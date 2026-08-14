# Scanpy 原生 batch-balanced kNN 图

本仓库把锁定版 BBKNN 的按批次配额近邻图能力迁移进锁定版 Scanpy，形成一个
Harbor single-step 算法迁移题。Agent 修改 `/testbed` 中的 Scanpy；独立 verifier
对比“原 Scanpy + 原 BBKNN”和“修改后的 Scanpy”。

## 当前状态

状态：`accepted`。

- Scanpy：`fabadb9412c0d1cd9df9d9c2e95ac266d564ee18`；
- BBKNN：`95ce34b8905cbde307704a77436c354938ba0367`；
- Python 3.12.11，Scanpy `1.14.0.dev21+gfabadb941`；
- 两个离线 wheel manifest 完全相同，SHA-256 为
  `1acf8933308ecd19873eecf25e9d1cf08e0564cb948b9385612813dbc08e011c`。

## 受限算法范围

- 给定 `adata.obsm[use_rep]` 中已计算好的 PCA/embedding，不把 PCA 本身纳入迁移；
- 每个 query cell 从每个 batch 恰好选择 `neighbors_within_batch` 个邻居；
- 支持精确 Euclidean 和 cosine 距离，不允许近似索引；
- batch label 必须是非空字符串；每个 batch 至少有 `neighbors_within_batch` 个 cell；
- cosine 输入中的每一行必须具有非零范数；
- 距离相同则按字符串 cell ID 的字典序打破平局，与输入行顺序无关；
- 自身属于自身 batch 的候选池，因此可占该 batch 的一个零距离名额，与 BBKNN
  的配额语义一致。

宿主 API 为 `scanpy.pp.batch_balanced_neighbors`。它写入 CSR distance/
connectivity 矩阵，并在 `adata.uns[key_added]` 保存按 canonical batch 顺序排列的
三维邻居索引和距离。

## 隔离模型

Agent 环境包含原始 Scanpy `/testbed`、只读 BBKNN 源码与公开样例，供阅读和实现。
Harbor 收集修改后的 `/testbed` 后停止 Agent 环境，再启动独立 verifier。Verifier
先在私有 reference 区运行锁定 BBKNN，随后删除 reference/donor，并以非 root UID
运行候选 Scanpy。候选阶段不能联网、不能 import BBKNN、不能读取 `/tests`，也不能
修改 `/testbed`。

## Reference 与评分

Verifier 动态运行锁定 BBKNN；9/15 个隐藏用例的 Euclidean 选邻居直接调用
`bbknn.matrix.get_graph(..., computation="cKDTree")`，全部 connectivity 均调用
锁定 BBKNN 的 UMAP graph routine。原 BBKNN 无法正确覆盖的限定边界按题面数学契约
处理：精确 cosine、cell-ID tie-break，以及其 `k=1` shape bug。

15 个隐藏用例等权计分，比较 neighbor cell ID、距离、CSR distance graph 和
connectivity graph。距离容差 `1e-8`，connectivity 容差 `1e-6`。API、输入拒绝、
逐 batch 配额、row permutation、dense/sparse、Scanpy 回归和隔离均为硬门。

## 验收结果

2026-08-14 最终直接容器验证：

- clean-room Oracle：`15/15`，Reward `1.0`；
- pristine Scanpy NOP：Reward `0.0`；
- 忽略 batch 配额的 global-kNN near miss：`0/15`，Reward `0.0`；
- 公开样例：`5/5`；
- 原 Scanpy neighbors 回归：`15 passed`、`4 skipped`；
- 最大隐藏距离误差 `8.88e-16`，connectivity 最大误差 `0`。

Harbor 0.20 正式验收：

- Oracle：1 trial、0 exception、`15/15`、Reward `1.0`，3 分 6 秒；
- NOP：1 trial、0 exception、Reward `0.0`，1 分 17 秒。

机器可读证据位于 `validation/evidence/`。

## 使用 Harbor

```bash
harbor run -p . -a oracle -n 1 --job-name algobridge-0001-oracle
harbor run -p . -a nop -n 1 --job-name algobridge-0001-nop
```

要求 Linux x86_64、Docker 或 Harbor 兼容容器后端、约 16 GB 内存和 30 GB 临时
存储；无需 GPU 或 H200 本地 bind mount。仓库与固定的
`python:3.12.11-slim-bookworm` 基础镜像就绪后，构建与试验均可离线运行。没有
cgroup 的 rootless Docker 环境添加 `--cpus ignore --memory ignore`。
