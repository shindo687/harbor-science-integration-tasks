# AlphaFold 2 原生 GNM/ANM 正常模态分析

本仓库是一道已验收的 Harbor single-step 算法迁移题：Agent 在锁定的
AlphaFold 2 源码中实现 ProDy 兼容的 Gaussian Network Model（GNM）与
Anisotropic Network Model（ANM）；独立 verifier 动态比较“原 AlphaFold
结构解析 → 原 ProDy”和“修改后的 AlphaFold”。候选实现最终不得依赖或调用
ProDy。

## 当前状态

状态：`accepted`。

- AlphaFold 2：commit `c77e5d2a8961d1a353632c462914ff0a32a950f6`；
- ProDy：commit `7969f497a8961253e2b4ac70255f3843e1ac0980`，即
  `v2.6.1-510-g7969f497`；
- reference wheel 由该 ProDy commit 构建，不用 PyPI 近似替代；
- 两份源码均记录 git tree、文件数、archive SHA-256，全部离线 wheels 在
  安装前严格校验 SHA-256；
- CPU-only，不需要 AlphaFold 模型参数、GPU、H200、本机目录映射或运行期网络。

这是对已预测 PDB/mmCIF 结构的后处理任务，不执行 AlphaFold 推理。

## Agent 要实现的接口

只允许新增 `alphafold/common/normal_modes.py`，其中提供：

```python
analyze_normal_modes(
    protein,
    *,
    model="gnm",
    chain_indices=None,
    cutoff=10.0,
    gamma=1.0,
    plddt_threshold=None,
    n_modes=5,
) -> dict
```

输入是官方 AlphaFold `Protein`，支持 PDB/mmCIF、链选择、C-alpha
pLDDT/B-factor 过滤、cutoff、gamma 和非零模态数量。输出包括 residue mapping、
GNM Kirchhoff/ANM Hessian、零模态数、eigenpairs、MSF 和 normalized
cross-correlation。范围不包括 AlphaFold 推理、MD trajectory、ensemble PCA、
membrane model 或 deformation sampling。

## 真实 reference 与隔离

Verifier 先用锁定的官方 AlphaFold `Protein` parser 读取结构，再实际调用锁定
ProDy 的 `GNM.buildKirchhoff`、`ANM.buildHessian`、`calcSqFlucts` 和
`calcCrossCorr` 生成 reference。没有 FakeRunner 或预存隐藏答案。

Reference 完成后，verifier 物理删除 ProDy runtime/source、reference runner、
wheelhouse 和 pristine host，再以 UID 10001、只读 `/testbed`、无网络运行候选。
源码策略只允许新增目标模块，并拒绝 donor import、外部进程、动态加载、网络
访问、无关源码修改及大段 donor token 复制。

`task.toml` 使用 schema 1.3 并显式收集 `/testbed` artifact。在
`environment_mode = "separate"` 下，Agent 容器停止、源码导出完成后，Harbor
才创建 verifier 容器；只有修改后的 AlphaFold 源码树跨越边界。

为了不引入约 80 MB、此题完全用不到的 JAX 计算后端，两个环境只提供锁定
AlphaFold residue constants 导入所需的最小 `jax.tree.map` 兼容层；结构解析仍是
官方 AF2 代码，该兼容层不模拟模型推理或数值算法。

## 评分与验收

15 个隐藏点覆盖 GNM/ANM、PDB/mmCIF、多链、missing C-alpha、pLDDT
过滤、断开 domain、gamma scaling、简并 eigenspace、residue gap，以及刚体平移
和旋转。除差分比较 network、eigenvalue、mode subspace、MSF 与 correlation
外，还检查对称性、行和、平移零模态、正交性、eigenpair residual 和统计一致性。

直接容器校准：

- clean-room Oracle：`15/15`，Reward `1.0`；
- pristine AlphaFold NOP：Reward `0.0`；
- GNM 正确但 ANM 错用 isotropic Cartesian spring：`8/15`，Reward
  `0.5333333333`，全部隔离/API hard gate 通过；
- 完整算法但 import ProDy：源码 hard gate，Reward `0.0`；
- 由真实 reference 生成的公开示例：`5/5`。

Harbor 0.20 正式验收：Oracle 和 NOP 各 1 trial、均为 0 exception/retry，
Rewards 分别为 `1.0` 和 `0.0`，两次 `/testbed` artifact collection 均为 `ok`。
最终 job/trial/lock/verifier 快照位于 `validation/evidence/`。

## 使用 Harbor

```bash
harbor run --path . --agent oracle --job-name algobridge-0018-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0018-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

需要 Linux x86_64、Docker/兼容后端、约 16 GB 内存和 20 GB 临时存储。基础
镜像首次获取可能联网；Agent 与 verifier 的依赖安装及题目运行均为离线。
