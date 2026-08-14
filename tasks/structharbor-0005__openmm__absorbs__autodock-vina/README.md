# STRUCTHARBOR-0005: OpenMM absorbs AutoDock Vina

已验收的 Harbor single-step algorithm-migration Task：Agent 在锁定的 OpenMM
8.4.0 源码中原生实现 AutoDock Vina 1.2.7 的固定 pose 打分与坐标力分析，最终
实现不能调用、导入、打包或依赖 AutoDock Vina。

## 限定范围

输入是已完成 Vina XS 类型标注的 receptor/ligand 原子和固定笛卡尔坐标。Task
覆盖五个默认 Vina 势能项、逐原子对分解、距离 cutoff、可旋转键归一化及坐标
力；不包含原子类型推断或 docking search。因此无需 GPU、模型权重或外部分子
文件。完整 API 与输入输出契约见 [`instruction.md`](instruction.md)。

## 真实参考与隔离

独立 verifier 的 reference 不是手写公式或 Fake。root-only 的本地 C++ 适配器
直接实例化锁定 AutoDock Vina 1.2.7 的 `vina_gaussian`、`vina_repulsion`、
`vina_hydrophobic` 和 `vina_non_dir_h_bond` 类，对每个原子对返回五项加权势能
与对称径向导数。

候选模块由 UID 10001 运行，不能读取 reference 二进制、Vina donor 源码、隐藏
测试、pristine OpenMM 或源码归档。Agent 和 verifier 都禁止联网，且使用
`environment_mode = "separate"`。Verifier 还要求 OpenMM 原文件逐字节不变，
只允许新增一个纯 Python 模块，并禁止动态加载、进程调用和非 `math` 依赖。

## 验收结果

| 实现 | 公开 | 隐藏 | 无效输入 | Reward |
|---|---:|---:|---:|---:|
| clean-room Oracle | 5/5 | 15/15 | 10/10 | 1.0 |
| pristine OpenMM（NOP） | — | — | — | 0.0 |
| 忽略扭转归一化的 near miss | 2/5 | 4/15 | 10/10 | 0.2667 |

正式 Harbor 0.20 Oracle/NOP 均一次完成、零异常。Oracle 的最大能量绝对误差
为 `4.44e-16 kcal/mol`（逐 pair term），最大坐标力绝对误差为
`2.14e-10 kcal/mol/angstrom`。机器可读证据和 trial 标识见
[`validation/HARBOR_ACCEPTANCE.md`](validation/HARBOR_ACCEPTANCE.md)。

## 锁定来源

- Host：OpenMM `8.4.0`，commit
  `47684368dbbe4185d068be77d32a962059cfc37c`，2,214 个 tracked files。
- Donor：AutoDock Vina `1.2.7`，commit
  `8eb40404f4f45608acb3b01427587ac049f27c1f`，308 个 tracked files。
- Base image：固定 digest 的 CPython 3.13 slim trixie。
- Reference adapter：可从锁定 donor 源码重复构建，二进制 SHA-256 为
  `4e369cfee5681168ba8db223d4cd46199187878470c87e19ae5d19ccd9248dd2`。

完整 commit、Git tree、archive 文件数与 SHA-256 见
[`source-lock.json`](source-lock.json)。

## 运行

```bash
harbor run --path . --agent oracle \
  --job-name structharbor-0005-oracle --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop \
  --job-name structharbor-0005-nop --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes
```

Agent 完成模块后可在其容器内运行五个公开样例：

```sh
/opt/task-tools/run-public-examples
```

需要 Linux x86_64 和 Docker/兼容后端，建议 4 CPU、8 GB 内存与 12 GB 临时
存储。无需 GPU，也不依赖 H200 上的本地路径映射。
