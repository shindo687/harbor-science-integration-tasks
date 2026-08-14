## 任务

在 `/testbed` 中的 **Scanpy** 仓库实现原生 batch-balanced kNN 图。

你可以阅读 `/opt/bbknn-source` 中锁定的 BBKNN 源码来理解原工作流，但最终实现
不得在运行时调用、import、链接、下载或 vendor BBKNN，也不得从 `/opt`、`/tests`
或网络加载隐藏实现。

## 必须提供的 API

从 `scanpy.pp` 导出：

```python
scanpy.pp.batch_balanced_neighbors(
    adata,
    *,
    batch_key,
    neighbors_within_batch=3,
    use_rep="X_pca",
    metric="euclidean",
    key_added="neighbors",
    copy=False,
)
```

函数遵循 Scanpy 的原地修改习惯；`copy=True` 时返回修改后的 `AnnData`，否则返回
`None`。

## 输入契约

- `adata.obsm[use_rep]` 是二维 dense `ndarray` 或 SciPy sparse matrix；算法必须
  将它解释为给定 embedding，不重新计算 PCA。
- `adata.obs_names` 是唯一 cell ID；tie-break 使用其字符串字典序。
- `adata.obs[batch_key]` 的值是非空字符串；batch 顺序是去重后的字符串字典序。
- `neighbors_within_batch` 是正整数，每个 batch 至少包含这么多个 cell。
- `metric` 只接受 `"euclidean"` 或 `"cosine"`，两者都必须是精确搜索。
- 所有 embedding 值必须有限；cosine 模式拒绝零范数行。

无效输入应抛出 `ValueError`（缺失 AnnData key 可沿用合适的 `KeyError`）。

## 选择与图语义

对每个 query cell 和每个 batch，计算到该 batch 全部 cell 的距离，选择恰好
`neighbors_within_batch` 个。排序键为 `(distance, cell_id)`。query 自身可作为
自身 batch 的邻居。

把每批结果按 canonical batch 顺序拼接，再按 `(distance, cell_id)` 排列后，使用
Scanpy/UMAP fuzzy simplicial set 语义计算 connectivity。不得只返回邻居列表或
一个占位图；近邻选择、配额和图权重都属于核心实现。

## 输出契约

`key_added == "neighbors"` 时写入：

- `adata.obsp["distances"]`：shape `(n_obs, n_obs)` 的 CSR directed distance graph；
- `adata.obsp["connectivities"]`：shape `(n_obs, n_obs)` 的 CSR fuzzy connectivity；
- `adata.uns["neighbors"]`。

其他 `key_added`（例如 `"bb"`）使用 `"bb_distances"`、
`"bb_connectivities"` 和 `adata.uns["bb"]`。

`adata.uns[key_added]` 至少包含：

- `distances_key` 与 `connectivities_key`；
- `params`，记录 `batch_key`、`neighbors_within_batch`、`use_rep`、`metric`；
- `batch_order`：shape `(n_batches,)` 的字符串数组；
- `indices`：shape `(n_obs, n_batches, neighbors_within_batch)` 的整数数组，第二维
  与 `batch_order` 对齐，每个 batch 内按 `(distance, cell_id)` 排序；
- `neighbor_distances`：与 `indices` 同 shape 的浮点数组。

## 验证

公开样例位于 `/examples`，可运行：

```bash
/opt/task-tools/run-public-examples
```

Verifier 会运行 15 个隐藏用例，差分比较锁定的原 Scanpy+BBKNN reference 与候选
Scanpy，并检查：

- 邻居 ID 和每批配额完全一致；
- 距离误差不超过 `1e-8`，connectivity 误差不超过 `1e-6`；
- dense/sparse embedding 等价；
- 输入行重排后按 cell ID 还原，输出不变；
- duplicate/tie 按 cell ID 稳定；
- 原 Scanpy 回归测试仍通过；
- 候选源码与运行期不依赖 BBKNN。

编译失败、API 缺失、回归破坏或依赖/隔离门失败均为 0 分；其余得分是隐藏用例
通过率。
