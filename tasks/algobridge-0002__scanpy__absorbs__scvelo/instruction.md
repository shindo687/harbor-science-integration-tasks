# 任务

在 `/testbed` 中的 **Scanpy** 仓库实现：**Scanpy 原生 RNA velocity transition graph**。

将 **scVelo** 的 `scVelo deterministic velocity graph` 能力以独立、受限实现迁移到 Scanpy。实现不得在运行时调用、import、链接、下载或 vendor scVelo；不得复制许可证不兼容的 donor 代码。

## 必须实现的公开 API

在 `scanpy.tl` 导出：

```python
scanpy.tl.velocity_transition_graph(
    adata,
    *,
    vkey="velocity",
    xkey="Ms",
    neighbors_key="neighbors",
    n_neighbors=None,
    n_recurse_neighbors=1,
    gene_subset=None,
    sqrt_transform=False,
    transition_scale=10.0,
    use_negative_cosines=False,
    copy=False,
)
```

默认原地修改 `adata` 并返回 `None`；`copy=True` 时仅修改并返回副本。

## 算法范围

输入中已经给出 residual velocity layer；本题不拟合动力学参数。对固定 kNN
计算 residual velocity 与候选 cell-state displacement 的 centered-cosine，拆分正负图，
再计算指数核并逐行归一化。支持 1 或 2 跳确定性邻居展开、可选基因子集、平方根
符号变换，以及是否纳入负余弦；不重建邻居，不含动力学参数拟合和随机采样。

## 输入与输出

- 输入：`AnnData.layers[xkey]`、`AnnData.layers[vkey]` 与
  `adata.uns[neighbors_key]["distances_key"]` 指向的固定 CSR distance graph。
- 正图写入 `adata.obsp[f"{vkey}_graph"]`，值域 `(0, 1]`。
- 负图写入 `adata.obsp[f"{vkey}_graph_neg"]`，值域 `[-1, 0)`。
- row-normalized transition 写入 `adata.obsp[f"{vkey}_transitions"]`。
- 每个 cell 的最大正余弦写入 `adata.obs[f"{vkey}_confidence"]`；无正边为 0。
- self-transition 概率写入 `adata.obs[f"{vkey}_self_transition"]`。
- 参数写入 `adata.uns[f"{vkey}_transition_params"]`。

输入须为有限实数、非空二维 layer；固定 graph 必须是 shape 匹配、无负权、无
self edge 且每行非空的 CSR。`gene_subset` 可为基因名序列或长度 `n_vars` 的布尔
mask。`n_neighbors` 若给出则必须为正整数，并按距离、再按 cell index 进行稳定截断。

## 差分 oracle

- Reference A+B：锁定 Scanpy 持有真实 `AnnData`，锁定 scVelo 的
  `velocity_graph` 与 `transition_matrix` 在 deterministic mode 动态计算结果。
- Candidate：只运行修改后的 Scanpy。
- 比较：CSR support 精确比较，图/transition 权重 `1e-6`，confidence `1e-7`；
  固定零范数、负相关、邻居展开和排序策略。

除数值差分外，Verifier 必须检查以下科学/数学不变量：

- transition 每个非空行的绝对值和为 1；不启用负余弦时普通行和也为 1
- 正负图 support 不重叠
- 整体表达缩放不改变余弦 transition

## Fixtures

分叉流形、静止细胞、负相关边、零 velocity、基因子集和邻居重排。

## 禁止事项与验收

- Candidate 阶段无网络且不存在可导入的 scVelo；不得调用、import、链接、下载、
  启动子进程执行或 vendor scVelo。
- 不得写死公开/隐藏 expected values，不得读取 verifier 私有路径。
- 必须保持 Scanpy 既有 API；请为新增功能添加宿主侧测试。
- 可阅读 `/opt/scvelo-source` 作为学习材料，并运行
  `/opt/task-tools/run-public-examples` 检查 5 个公开样例。

## 非胶水判定

需要实现向量 residual、稀疏图打分和概率归一化，不是 layer 改名。

论文共现证据：`Scanpy -> scVelo`，出现在 17 篇论文中。题目实现必须保持宿主现有公共 API/回归测试，不做无关重构。
