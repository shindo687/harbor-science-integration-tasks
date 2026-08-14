# OpenMM 原生 reversible Markov state model

本仓库是一道已验收的 Harbor single-step 算法迁移题：Agent 在锁定的
OpenMM 源码中实现离散 Markov state model API；独立 verifier 动态对比
“原 OpenMM 工作流 → 原 PyEMMA”和“修改后的 OpenMM”。候选实现最终不得
依赖或调用 PyEMMA、deeptime 或 msmtools。

## 当前状态

状态：`accepted`。

- OpenMM：commit `c6173db6e8edd705eb59172bd21e9ce69c572405`；
- PyEMMA：commit `3327f28b49e388e1ce4a6a83ab2f0c0ac7ca5050`，即
  `v2.5.12-6-g3327f28b`；
- reference wheel 直接由该 commit 构建，版本
  `2.5.12+6.g3327f28b`，不是用 PyPI 近似替代；
- 两份源码均记录 git tree、文件数、archive SHA-256；所有离线 wheel 在
  安装前执行严格 SHA-256 校验；
- CPU-only，无 GPU、H200、本机路径或运行期网络依赖。

## Agent 要实现的接口

在 `wrappers/python/openmm/app/markov_model.py` 中实现并公开导出：

```python
estimate_markov_model(
    trajectories,
    lag=1,
    count_mode="sliding",
    reversible=True,
    connectivity="largest",
) -> dict
```

范围包括 sliding/sample lagged counts、最大无向连通集、非可逆行归一 MLE、
reversible constrained MLE、stationary distribution、复数谱和 implied
timescales。状态标签可以不连续；不包括 TICA、聚类、PCCA、Bayesian MSM 或
分子轨迹特征化。

输出键为 `active_set`、`count_matrix`、`transition_matrix`、
`stationary_distribution`、`eigenvalues`（JSON 友好的 `[real, imag]`）和
`timescales`。

## 真实 reference 与隔离

Verifier 的 reference runner 调用锁定 PyEMMA 的
`pyemma.msm.estimate_markov_model`。该 PyEMMA commit 内部确实把 transition
matrix estimation 委托给锁定 `deeptime==0.4.5`；两者都只存在于
`/opt/reference-runtime`。

Reference 计算完成后，verifier 物理删除 reference runtime、PyEMMA 源码、
wheelhouse、pristine host、reference runner 和候选物化工具。随后只把 Agent
提交的单个模块 overlay 到已锁定 OpenMM runtime，以 UID 10001、无网络运行。
源码策略只允许新增 MSM 模块和追加公共导出，并拒绝 donor import、外部进程、
动态加载、网络访问或无关源码修改。

`task.toml` 使用 schema 1.3，显式声明 `/testbed` artifact；在
`environment_mode = "separate"` 下，Agent 容器停止并收集源码后才启动 verifier
容器。只有修改后的 OpenMM 树跨越该边界。

## 评分与验收

15 个隐藏点覆盖二/三/四态模型、sliding/sample、lag 1/2/3、多 trajectory、
不连续标签、断开分量、周期链以及 reversible/non-reversible 模型。每点比较
active set、精确 counts、transition/stationary、复数 eigenvalues 和 timescales，
并检查 row stochastic、stationarity、detailed balance 与 spectral consistency。

直接容器校准：

- clean-room Oracle：`15/15`，Reward `1.0`；
- pristine OpenMM NOP：Reward `0.0`；
- 简单行归一 `C + C.T` near miss：`10/15`，Reward `0.6666666667`，所有
  隔离/API hard gate 通过；
- 完整算法但 import PyEMMA：源码 hard gate，Reward `0.0`；
- 公开示例：`5/5`。

Harbor 0.20 正式验收：Oracle 1 trial、0 exception/retry、`15/15`、Reward
`1.0`（44 秒）；NOP 1 trial、0 exception/retry、Reward `0.0`（42 秒）；两次
`/testbed` artifact 均为 `ok`，且两个 task lock 的 digest 完全相同。最终
job/trial/lock/verifier 报告位于 `validation/evidence/`。

## 使用 Harbor

```bash
harbor run --path . --agent oracle --job-name algobridge-0016-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0016-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

需要 Linux x86_64、Docker/兼容后端、约 16 GB 内存和 20 GB 临时存储。基础
镜像首次获取可能联网；随后 Agent 与 verifier 的 Python 安装和运行均离线。
