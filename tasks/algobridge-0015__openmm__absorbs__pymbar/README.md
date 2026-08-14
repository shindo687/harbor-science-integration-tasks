# OpenMM 原生 MBAR free-energy estimator

本仓库是一道已验收的 Harbor single-step 算法迁移题：Agent 在锁定的
OpenMM 源码中实现受限 MBAR 分析 API；独立 verifier 动态对比“原 OpenMM →
原 pymbar”和“修改后的 OpenMM”。最终实现不得依赖或调用 pymbar。

## 当前状态

状态：`accepted`。

- OpenMM 源码：`c6173db6e8edd705eb59172bd21e9ce69c572405`；
- pymbar：`ed40ec3bbef03bb08938ad1a74d459b0d1ab81f7`；
- 两份源码均以完整、确定性 `git archive` 物化，并记录 tree、文件数和 SHA-256；
- Python 3.12.11；离线 wheel 均在安装前执行严格 SHA-256 校验；
- CPU-only，不依赖 H200、GPU、宿主机路径或外部网络。

## 算法与接口

Agent 新增 `wrappers/python/openmm/app/mbar.py` 并从 `openmm.app` 导出：

```python
estimate_mbar(
    u_kn,
    N_k,
    *,
    initial_f_k=None,
    relative_tolerance=1e-10,
    maximum_iterations=10000,
) -> dict
```

限定范围包括稳定的自洽/Newton 求解、`f_k[0] = 0` gauge、MBAR 权重、
overlap、渐近协方差、自由能差不确定度、effective sample number 和收敛诊断。
不包括 timeseries subsampling、bootstrap、observable 或 FES。

返回键为 `f_k`、`Delta_f`、`dDelta_f`、`covariance`、`weights`、
`overlap`、`effective_sample_number`、`iterations`、`residual` 和
`converged`。

## Reference 与隔离

Verifier 用官方 OpenMM `Reference` CPU platform 对一维受限 oscillator systems
逐状态计算 reduced potentials，然后把同一 `u_kn/N_k` 交给锁定 pymbar 和候选
API。官方 `openmm==8.5.2` wheel 只承担这一步二进制能量求值；Agent 修改的宿主
仍是上面锁定的 OpenMM 8.6-development 源码。这个兼容 runtime 已单独锁定并在
`THIRD_PARTY.md` 中明确记录，没有被冒充为源码 commit。

Reference 计算完成后，verifier 删除 pymbar、pristine host、reference runner、
源码 archive 和物化工具，再把候选目录改为只读，以 UID 10001 运行候选。
候选看不到 `/tests`，不能联网；源码扫描禁止调用 donor、外部进程、动态加载、
网络库、SciPy/numexpr，并检查 donor token 片段和修改范围。

只有 `/testbed` 从 Agent 容器进入 separate verifier。pymbar 和公开样例都不会
成为 artifact。

## 评分

15 个隐藏点等权：

- 12 个动态数值点：高/低 overlap、样本数不等、三态 bridge、unsampled state、
  重复样本、极端 state offset、共同 sample offset、warm start、近相同状态、
  四态 ladder 和非对称 stiffness；
- 3 个非法输入拒绝点。

差分比较 free energy、权重、overlap、协方差、不确定度和 effective sample
number，并检查反对称/路径可加、权重归一、overlap row-stochastic、协方差 PSD、
共同 sample offset 不变性及收敛残差。源码/API/隔离/宿主回归任一 hard gate
失败均为 0；否则 Reward 为隐藏点通过率。

## 验收结果

2026-08-14 直接容器验证：

- clean-room Oracle：`15/15`，Reward `1.0`；
- pristine OpenMM NOP：Reward `0.0`；
- 使用 `W.T @ W` 近似协方差的科学 near miss：`3/15`，Reward `0.2`，且所有
  hard gate 通过；
- 公开样例：`5/5`。

Harbor 0.20 正式验收：

- Oracle：1 trial、0 exception、0 retry、`15/15`、Reward `1.0`，44 秒；
- NOP：1 trial、0 exception、0 retry、Reward `0.0`，39 秒；
- 两个 job 锁定的输入 task digest 相同：
  `sha256:b826fc51231587fa9b6e7faadbb1f537a1009c4b14372e589ec6e462d873eb38`；
- 两次 `/testbed` artifact 状态均为 `ok`。

正式 Oracle 的最大绝对误差：`f_k/Delta_f 6.78e-12`、weights
`7.77e-14`、overlap `1.30e-12`、covariance `5.69e-11`。机器可读报告位于
`validation/evidence/`。

## 使用 Harbor

```bash
harbor run --path . --agent oracle --job-name algobridge-0015-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0015-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

需要 Linux x86_64、Docker/兼容后端、约 16 GB 内存和 20 GB 临时存储。固定
基础镜像就绪后，Agent 与 verifier 安装和运行都不访问网络。
