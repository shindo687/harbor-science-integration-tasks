# ALGOBRIDGE-0003: Seurat absorbs Monocle3

已验收的 Harbor single-step algorithm-migration Task：Agent 在锁定的 Seurat
源码中原生实现给定 principal graph 上的细胞投影、root 定向 pseudotime、分支
状态和顶点角色，最终实现不能调用或依赖 Monocle3。

## 参考链路

Verifier 并非使用 FakeRunner。它针对每个输入创建真实 Monocle3
`cell_data_set`，注入 embedding 与 principal graph，随后实际执行锁定
Monocle3 1.4.26 的 `project2MST` 和 `order_cells`。候选实现由 UID 10001 的
独立进程执行；该用户不能读取 Monocle3 包、donor 源码、pristine Seurat 或
隐藏测试，运行时也不能联网。

范围刻意限定为已给定的小型 2D/3D principal graph；图学习、表达矩阵预处理
和 Seurat object 修改不在本题范围内。公开 API、输入约束和输出语义见
[`instruction.md`](instruction.md)。

## 验收结果

| 实现 | 公开 | 隐藏 | 无效输入 | 变形测试 | Reward |
|---|---:|---:|---:|---:|---:|
| clean-room Oracle | 5/5 | 15/15 | 10/10 | 2/2 | 1.0 |
| pristine Seurat（NOP） | 0/5 | 0/15 | 10/10 | 0/2 | 0.0 |
| 错用 Euclidean cell-chain 权重的 near miss | 3/5 | 5/15 | 10/10 | 1/2 | 0.3333 |

Oracle 的 pseudotime 在全部 20 个有效差分用例中与真实参考逐项一致，最大绝对
误差为 `0`；closest vertex、cell state、vertex role 和 root 也完全一致。
正式 Harbor Oracle/NOP 均为一次完成、零异常。机器可读证据与 trial 标识见
[`validation/HARBOR_ACCEPTANCE.md`](validation/HARBOR_ACCEPTANCE.md)。

## 源码与离线边界

- Host：Seurat `5.5.1.9000`，commit
  `258a250c7b27e70f6651443d9835cd3c289c51ee`。
- Donor：Monocle3 `1.4.26`，commit
  `4f4239a0afb0dd1941a0359ba6bec95eb0ccf628`。
- Reference image：固定 digest 的 Biocontainers `r-monocle3` 镜像。
- 两份完整 Git source archive、文件数、tree 与 SHA-256 记录在
  [`source-lock.json`](source-lock.json)。

Agent 镜像提供完整 Seurat 源码、只读 donor 源码、题面和 5 个公开样例；独立
verifier 镜像持有真实参考、15 个隐藏用例和评分器。两个运行阶段均为
`network_mode = "no-network"`，且 `environment_mode = "separate"`。

## 运行

```bash
harbor run --path . --agent oracle \
  --job-name algobridge-0003-oracle --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop \
  --job-name algobridge-0003-nop --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes
```

Agent 完成 API 后可在其容器内运行公开检查：

```sh
/opt/task-tools/run-public-examples
```

需要 Linux x86_64 与 Docker/兼容后端，建议 8 GB 内存和 16 GB 临时存储；
不需要 GPU 或 H200。首次拉取锁定基础镜像需要宿主机能访问 Quay，镜像构建与
Agent/verifier 运行阶段本身不下载依赖。
