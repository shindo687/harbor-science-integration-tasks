# ALGOBRIDGE-0002: Scanpy absorbs scVelo

本仓库是一个 Harbor single-step 算法迁移题：Agent 在锁定版 Scanpy 中实现原生、
确定性的 RNA velocity transition graph；独立 verifier 差分比较“原 Scanpy + 原
scVelo”和“修改后的 Scanpy”，候选运行时不含 scVelo。

状态：`accepted`。

## 锁定输入与算法边界

- Scanpy commit：`fabadb9412c0d1cd9df9d9c2e95ac266d564ee18`；
- scVelo commit：`f63c0e70596ced2f1bee8cf07e8ab66037cf86b2`；
- host tree：`c68e70c22539158ed52fd8169761d818ac8510a2`；
- donor tree：`50237cef428c6bf42611522d8721983847af4584`；
- Python 3.12.11，Scanpy `1.14.0.dev21+gfabadb941`，scVelo
  `0.3.3+locked.f63c0e7`；
- Agent/verifier 的离线 wheel manifest 相同，SHA-256 为
  `df376d88fafc302e72207e4e74b1f93627a43b79307fa222d16f5992cb00a155`。

任务输入是真实 `AnnData` layers 和固定 CSR 邻居图。Agent 实现 centered cosine、
正负 velocity graph、指数 transition kernel、绝对值行归一化、1/2 跳邻居展开、
基因子集和 signed square-root 变换；不包含动力学参数拟合、邻居重建或随机采样。

## 隔离与差分评分

Agent 镜像包含 `/testbed` Scanpy、只读 `/opt/scvelo-source` 学习源码、五个公开样例
和完整离线依赖。Harbor 仅收集 `/testbed`，停止 Agent 环境后再创建 separate
verifier。Verifier 动态运行锁定 Scanpy→scVelo reference，扫描候选变更，物化
候选 runtime，物理删除 reference/donor/wheel 私有材料，然后以 UID 10001 从只读
树运行候选。此时 scVelo 不可 import，`/tests` 不可读，且网络关闭。

15 个隐藏点比较正图、负图和 transition 的 CSR support 与数值；图和 transition
容差 `1e-6`，confidence/self-transition 容差 `1e-7`。还检查正负 support 不重叠、
transition 绝对行和为 1、整体表达缩放不变量、API 拒绝路径、copy 语义和候选回归。
任何来源完整性、clean-room、隔离、API 或回归硬门失败，Reward 都为 0。

## 验收结果

2026-08-14 最终结果：

| 基线 | 隐藏点 | Reward | 硬门 |
| --- | ---: | ---: | --- |
| Clean-room Oracle | 15/15 | 1.0 | 6/6 通过 |
| 原始 Scanpy NOP | 0/15 | 0.0 | 预期缺少实现 |
| 未中心化 cosine near miss | 0/15 | 0.0 | 6/6 通过 |
| 公开样例 | 5/5 | — | 通过 |

正式 Harbor 0.20 验收：

- Oracle：1 trial、0 exception、0 retry、Reward `1.0`，约 57 秒；
- NOP：1 trial、0 exception、0 retry、Reward `0.0`，约 50 秒；
- 两次使用完全相同的最终 task content digest；
- 两次 `/testbed` artifact 均为 `status=ok`。

机器可读报告位于 `validation/evidence/`。

## 目录与运行

```text
instruction.md       Agent 任务契约
environment/         Agent 镜像、锁定源码、学习 donor、公开样例
tests/               独立 verifier、锁定 reference runner、15 个隐藏 fixtures
solution/            作者 Oracle，不进入 Agent 或 verifier 镜像
validation/          NOP/near-miss 校准和验收证据
task.toml             separate/no-network/resources/artifact 规则
```

```bash
harbor run --path . --agent oracle --n-concurrent 1 --cpus ignore --memory ignore --yes
harbor run --path . --agent nop --n-concurrent 1 --cpus ignore --memory ignore --yes
```

任务只需 Linux x86_64、Harbor 0.20 和 Docker/兼容后端；CPU-only，无需 GPU、H200、
模型权重、数据库或宿主机路径 bind mount。基础镜像和仓库内容就绪后可完全离线构建。
建议为两个约 200 MB 的构建上下文及解包镜像预留 30 GB 临时容器存储。
