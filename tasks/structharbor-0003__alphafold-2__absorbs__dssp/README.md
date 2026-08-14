# STRUCTHARBOR-0003: AlphaFold2 absorbs DSSP

已验收的 Harbor single-step algorithm-migration Task：Agent 在锁定的
AlphaFold2 源码中原生实现 DSSP 兼容的主链氢键、二级结构、chain break、beta
bridge/ladder 与 bend 分析，最终实现不能调用或依赖 DSSP。

## 真实参考链路

Verifier 并非 Fake。它把同一组 AlphaFold 原生全原子数组转换成标准 PDB，随后
由 root-only 的真实 `mkdssp 4.4.11` 逐案计算 reference。候选模块由 UID 10001
的独立进程执行；该用户不能读取 `mkdssp`、DSSP donor 源码、pristine AlphaFold、
隐藏用例或源码归档，运行时也不能联网。

范围限定为 AlphaFold 已预测出的标准蛋白主链坐标，因此无需模型权重、MSA、
template、GPU 或 H200。公开 API 和输入/输出契约见
[`instruction.md`](instruction.md)。

## 验收结果

| 实现 | 公开 | 隐藏 | 无效输入 | Reward |
|---|---:|---:|---:|---:|
| clean-room Oracle | 5/5 | 15/15 | 10/10 | 1.0 |
| pristine AlphaFold2（NOP） | 0/5 | 0/15 | 不适用 | 0.0 |
| 关闭 beta bridge/ladder 的 near miss | 1/5 | 4/15 | 10/10 | 0.2667 |

Oracle 的二级结构 code 和所有 donor/acceptor partner 索引在 20 个有效差分
用例中逐项一致。能量最大差值为 `0.05`，对应 legacy mkdssp 输出仅保留一位
小数，而候选实现保留三位小数。正式 Harbor Oracle/NOP 均一次完成、零异常。
机器可读证据和 trial 标识见
[`validation/HARBOR_ACCEPTANCE.md`](validation/HARBOR_ACCEPTANCE.md)。

## 源码与离线边界

- Host：AlphaFold2 commit `c77e5d2a8961d1a353632c462914ff0a32a950f6`。
- Donor：DSSP `4.4.11` commit `3cbec3abea5169ea8fac030d0e43d28102b128aa`。
- Reference：原始 conda-forge `dssp 4.4.11 h629725b_0` 包及可离线运行的
  relocatable payload。
- Fixtures：RCSB PDB 的 1CRN、1ZDD、1TEN，原始文件 SHA-256 已锁定。
- Python/NumPy、基础镜像、源码 archive、CCD 和 reference runtime 均有固定
  URL/digest/SHA-256，详见 [`source-lock.json`](source-lock.json)。

Agent 镜像提供完整 AlphaFold2 源码、只读 donor 源码和 5 个公开样例；独立
verifier 镜像持有真实 reference 与 15 个隐藏用例。两个阶段均为
`network_mode = "no-network"`，且 `environment_mode = "separate"`。

## 运行

```bash
harbor run --path . --agent oracle \
  --job-name structharbor-0003-oracle --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop \
  --job-name structharbor-0003-nop --n-concurrent 1 \
  --cpus ignore --memory ignore --force-build --yes
```

Agent 完成模块后可在其容器内运行：

```sh
/opt/task-tools/run-public-examples
```

需要 Linux x86_64 和 Docker/兼容后端，建议 8 CPU、16 GB 内存与 20 GB
临时存储。不需要 GPU，也不依赖任何宿主机 H200 路径映射。
