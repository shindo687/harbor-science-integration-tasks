# STRUCTHARBOR-0004: AutoDock Vina absorbs RDKit

已验收的 Harbor single-step algorithm-migration Task：Agent 在锁定的 AutoDock
Vina 1.2.7 源码中原生实现 RDKit 2026.03.5 的 MMFF94 固定几何配体应变能，
最终实现不能调用、导入、打包或依赖 RDKit。

## 限定范围

输入是已经完成 MMFF94 类型标注、拓扑枚举和参数分配的 interaction packet，
其中包含笛卡尔坐标以及 bond、angle、stretch-bend、out-of-plane、torsion、
van der Waals 和 electrostatic 参数。Task 只迁移固定几何能量求值，不包含原子
类型推断、参数分配、构象生成、能量最小化或 docking search。完整 API 与输入
输出契约见 [`instruction.md`](instruction.md)。

## 真实参考与隔离

独立 verifier 的 reference 不是手写公式或 Fake。root-only reference 从锁定的
官方 RDKit wheel 导入 2026.03.5，构造真实 `MMFFMolProperties` 与
`MMFFGetMoleculeForceField`，并通过逐项开关分别计算七个原生 MMFF94 分量。

候选模块由 UID 10001 运行，不能读取 RDKit runtime、donor 源码、离线 wheels、
隐藏测试、pristine Vina 或源码归档。Agent 和 verifier 都禁止联网，并使用
`environment_mode = "separate"`。Verifier 还要求所有 Vina 原文件逐字节不变，
只允许新增一个纯 Python 模块，并禁止动态加载、进程调用和非 `math` 依赖。

## 验收结果

| 实现 | 公开 | 隐藏 | 无效输入 | 变形测试 | Reward |
|---|---:|---:|---:|---:|---:|
| clean-room Oracle | 5/5 | 15/15 | 12/12 | 2/2 | 1.0 |
| pristine Vina（NOP） | — | — | — | — | 0.0 |
| 遗漏 out-of-plane 的 near miss | 2/5 | 5/15 | 12/12 | 2/2 | 0.3333 |

正式 Harbor 0.20 Oracle/NOP 均一次完成、零异常。Oracle 在二十个分子上的七项
能量分解最大绝对误差为 `8.53e-14 kcal/mol`。机器可读证据、trial 标识、task
checksum 和 digest 见
[`validation/HARBOR_ACCEPTANCE.md`](validation/HARBOR_ACCEPTANCE.md)。

## 锁定来源

- Host：AutoDock Vina `1.2.7`，commit
  `8eb40404f4f45608acb3b01427587ac049f27c1f`，308 个 tracked files。
- Donor：RDKit `2026.03.5`，commit
  `de8add1e32ff6d3c4e4e406f64b703b662dff1d6`，6,197 个 tracked files。
- Reference runtime：官方 RDKit 2026.3.5 CPython 3.13 wheel 及锁定的 NumPy、
  Pillow 离线依赖。
- Base image：固定 digest 的 CPython 3.13 slim trixie。

完整 commit、Git tree、archive/wheel SHA-256 见
[`source-lock.json`](source-lock.json)。

## 运行

```bash
harbor run --path . --agent oracle \
  --job-name structharbor-0004-oracle --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop \
  --job-name structharbor-0004-nop --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes
```

Agent 完成模块后可在其容器内运行五个公开样例：

```sh
/opt/task-tools/run-public-examples
```

需要 Linux x86_64 和 Docker/兼容后端，建议 4 CPU、8 GB 内存与 12 GB 临时
存储。无需 GPU、外部模型或网络。
