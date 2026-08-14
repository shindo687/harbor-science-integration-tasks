# 任务：把 DockQ 与 ipSAE 原生集成到 ColabFold

工作目录 `/testbed` 是锁定在 ColabFold v1.6.1 commit
`277662d7f4b0e4356c8d3fc4aec7c5a074cc65ad` 的源码。请把 DockQ 复合物准确度
评估和 ipSAE 复合物置信度评估同时集成进 ColabFold 的标准批处理流程。

这是一道算法迁移题：只增加包装脚本、只修改输出文件、或继续调用下游程序均不算完成。
评分不会运行昂贵的神经网络推理，但会用仿真的多模型输出执行真实
`colabfold.batch.predict_structure` 函数体。

## 可用研究材料与提交边界

- DockQ commit `75db7ab4f6b824c70d120c5f620582e164ed5479` 的算法源码和
  MIT 许可证位于 `/opt/dockq`。
- DunbrackLab/IPSAE commit `6174cf9e71cb1bd660cc805856a18c4871a6dec3`
  的 `ipsae.py` 和 MIT 许可证位于 `/opt/ipsae`；脚本头部包含原作者的算法与
  命令行说明。
- 5 个公开输入/输出样例位于 `/examples`。完成接口后可运行：

  ```bash
  python3 /examples/verify_examples.py \
    /testbed/colabfold/alphafold/complex_metrics.py
  ```

- 环境全程断网；无需模型参数、MSA 服务或数据库。
- 最终只提交 `/testbed`。不得把 donor 源码复制进提交，也不得安装、导入、调用、
  链接或以子进程执行 DockQ/ipSAE。实现只能依赖 Python 标准库、NumPy 和 ColabFold
  已有依赖。

只允许修改 `colabfold/batch.py`，并新增
`colabfold/alphafold/complex_metrics.py`；其他锁定文件被删除或修改会触发 0 分门禁。

## 1. 原生计算接口

在 `colabfold/alphafold/complex_metrics.py` 实现以下两个函数。

### DockQ

```python
score_dockq(
    model_pdb,
    native_pdb,
    mapping=None,
    contact_cutoff=5.0,
    interface_cutoff=10.0,
) -> dict
```

`model_pdb` 和 `native_pdb` 可为 PDB 文本、字符串路径或 `pathlib.Path`。本题 DockQ
范围固定为两个蛋白链；映射后的残基序列完全相同。未提供 `mapping` 时必须搜索所有
序列兼容映射并选择 DockQ 最大者；映射方向为 `model_chain -> native_chain`。

结果必须恰好包含：

```text
fnat, iRMSD, LRMSD, DockQ, CAPRI,
native_contacts, preserved_contacts, mapping
```

语义与锁定 DockQ 一致：native contact 保留率、界面 RMSD、受体对齐后的 ligand
RMSD、连续 DockQ 和 CAPRI 标签。

### ipSAE

```python
score_ipsae(
    pae,
    plddt,
    model_pdb,
    pae_cutoff=15.0,
    distance_cutoff=15.0,
    iptm=None,
) -> dict
```

支持 2 个或更多蛋白链。`pae` 是 `N x N` 残基 PAE，`plddt` 是长度 `N` 的残基
pLDDT，顺序与 PDB 链/残基顺序一致。结果 schema：

```text
pae_cutoff, distance_cutoff, chain_pairs
```

每个无序链对必须按出现顺序产生两个 `type="asym"` 记录和一个 `type="max"` 记录。
每条记录必须恰好包含：

```text
chain1, chain2, type,
ipsae, ipsae_d0chn, ipsae_d0dom,
iptm_af, iptm_d0chn, pdockq, pdockq2, lis,
n0res, n0chn, n0dom, d0res, d0chn, d0dom,
nres1, nres2, dist1, dist2
```

数值语义与锁定 ipSAE v4 的 AF2/PDB 路径一致。

### CLI

同一模块还必须提供：

```bash
python3 colabfold/alphafold/complex_metrics.py \
  --model-pdb MODEL.pdb \
  [--native-pdb NATIVE.pdb] \
  [--scores-json SCORES.json] \
  --output RESULT.json
```

提供 native 时输出顶层 `dockq`，提供 scores 时输出顶层 `ipsae`；可同时输出。JSON
必须是标准 JSON，不得包含 `NaN`/`Infinity`。浮点字段按相对或绝对误差 `5e-4` 验收。

## 2. 接入 ColabFold 标准预测流程

扩展 `colabfold.batch.predict_structure(...)` 和 `run(...)`，增加向后兼容的尾部参数：

```python
run_dockq: bool = True
dockq_native_path: Optional[Union[str, Path]] = None
run_ipsae: bool = True
ipsae_pae_cutoff: float = 15.0
ipsae_distance_cutoff: float = 15.0
```

若 `dockq_native_path` 是目录，按 `<jobname>.pdb` 查找 native。CLI 还需暴露：

```text
--dockq-native-path
--run-dockq / --no-run-dockq
--run-ipsae / --no-run-ipsae
--ipsae-pae-cutoff
--ipsae-distance-cutoff
```

对每个预测模型，在生成 unrelaxed PDB 和 scores JSON 的同一后处理阶段计算指标，并在
原 scores JSON 中新增 `complex_metrics`：

```json
{
  "schema_version": 1,
  "dockq": { "status": "...", "reason": null, "dockq": null, "...": null },
  "ipsae": { "status": "...", "reason": null,
             "pae_cutoff": 15.0, "distance_cutoff": 15.0,
             "chain_pairs": [] }
}
```

DockQ 记录的键必须恰好为：

```text
status, reason, dockq, fnat, irms, lrms, capri,
native_contacts, preserved_contacts, mapping
```

- 成功：`computed` / `reason=null`；
- 未提供 native：`not_computed` / `native_structure_not_provided`；
- 用户关闭：`disabled` / `disabled_by_user`；
- 计算异常：`error` / 非空诊断文本，数值字段为 `null`。

ipSAE 记录的键必须恰好为：

```text
status, reason, pae_cutoff, distance_cutoff, chain_pairs
```

- multimer 且有 PAE：`computed`；
- 单链：`not_applicable` / `single_chain_prediction`；
- 没有 PAE：`not_computed` / `predicted_aligned_error_not_available`；
- 用户关闭：`disabled` / `disabled_by_user`；
- 计算异常：`error` / 非空诊断文本。

在重排完成后还要生成 `<jobname>_complex_metrics.json`，顶层按最终 rank 名称索引，
内容与对应 scores JSON 中的记录完全一致；`predict_structure` 的返回值增加
`complex_metrics`，且保留所有原有返回项和预测产物。

## 3. 隐藏评分与防作弊

独立、断网 verifier 会先运行锁定的原 DockQ 与原 ipSAE 生成动态参考值，然后物理删除
两套 donor，再以 UID 10001 执行候选。候选阶段没有 donor 可执行文件、Python 包、源码、
动态库或网络，也无法读取 reference 和期望值。

以下为 0 分硬门禁：编译/接口失败、导入或调用 donor/外部运行时、vendor donor、破坏
锁定 ColabFold 文件、或破坏原标准预测产物。通过门禁后，分数为 15 个隐藏用例的
通过率；例如通过 12/15 得 0.8。
