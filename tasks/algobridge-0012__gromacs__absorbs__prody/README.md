# ALGOBRIDGE-0012：GROMACS 原生 ANM 分析

状态：`accepted`。这是一道 CPU-only、离线、single-step Harbor 算法迁移题：
要求 Agent 在锁定 GROMACS 的 gmxapi 源码中实现 C-alpha anisotropic network
model（ANM），候选执行时不得调用或依赖 ProDy、SciPy 或其他 elastic-network
实现。

## 能力边界与差分模型

锁定的 GROMACS 已有力场 Hessian normal-mode 计算和 eigensystem 分析，但没有
从选定坐标直接构造 coarse-grained ANM Hessian、MSF 与 cross-correlation 的
接口；本题因此不是复刻现有 `gmx nmeig`。

```text
GROMACS nm 坐标/ordered selection → 锁定 ProDy ANM → 参考结果
                                                        │
修改后的 gmxapi → analyze_anm                           ├─ 差分比较
                                                        │
                 数学不变量与隔离门禁 ──────────────────┘
```

Agent 只能新增：

```text
python_packaging/gmxapi/src/gmxapi/analysis/__init__.py
python_packaging/gmxapi/src/gmxapi/analysis/anm.py
```

API、GROMACS nm 单位、Hessian block 约定、`1e-6` 零模阈值和返回字段见
`instruction.md`。

源码被精确固定为：

- GROMACS `6507818c312391b763d56bc43e03e00fc1ed8bd0`；
- ProDy `7969f497a8961253e2b4ac70255f3843e1ac0980`，reference wheel 2.6.1；
- Python 基础镜像：`python:3.10.18-bookworm`，使用 digest 固定。

源码归档、tree、wheel 与依赖 manifest 的 SHA256 位于 `source-lock.json`。
许可证与 donor 边界见 `THIRD_PARTY.md`。

## 隔离与评分

`task.toml` 设置 `environment_mode = "separate"` 和 `network_mode =
"no-network"`。Harbor 先运行 Agent 并收集 `/testbed`，关闭 Agent 容器后再启动
独立 verifier。

Verifier 先用真实锁定 ProDy 计算全部参考结果，然后：

1. 只允许新增两个指定文件，并检查禁止依赖、执行原语和 donor token 片段；
2. 把 `/testbed` 设为只读；
3. 物理删除 ProDy runtime/source、reference runner、wheel、SciPy/Biopython 和
   pristine host；
4. 以无写权限的 UID 10001、无网络环境执行候选；
5. 检查非法输入以及 rigid transform、gamma scaling、atom reorder 硬门禁；
6. 对 15 个隐藏网络逐例比较并评分。

任一硬门禁失败得 0，否则 Reward 为通过数除以 15。逐例比较 Hessian、
eigenvalues、简并 eigenspace projector、covariance、MSF、cross-correlation、
selection mapping、component 和 zero-mode diagnostics；另行检查 Hessian 对称性、
block translation sum rule、PSD、mode orthogonality/eigen residual、covariance
重建与统计一致性。

## 验收结果

| 实现 | 结果 | Reward |
|---|---:|---:|
| clean-room Oracle | 15/15 | 1.0 |
| pristine GROMACS（NOP） | source gate | 0.0 |
| 缺少距离归一化的 near miss | 0/15 | 0.0 |
| 直接 import ProDy | dependency gate | 0.0 |
| 公开样例 | 5/5 | — |

正式 Harbor 0.20 Oracle 与 NOP 各完成 1 个 trial，均为 0 exception、0 retry，
Rewards 分别为 `1.0` 和 `0.0`，两次 `/testbed` artifact collection 均为
`ok`。机器可读 job、trial、lock、artifact 和 verifier 报告保存在
`validation/evidence/`。

在 Agent 环境实现 API 后，可回放 5 个由锁定 reference 生成的公开 fixture：

```bash
/opt/task-tools/run-public-examples
```

## 使用 Harbor

```bash
harbor run --path . --agent oracle --job-name algobridge-0012-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0012-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

需要 Linux x86_64、Docker/兼容后端、约 16 GB 内存和 20 GB 临时存储；不需要
GPU 或 H200。基础镜像首次获取可能联网，但镜像构建中的依赖安装、Agent 和
verifier 执行均使用仓库内锁定材料且不访问网络。
