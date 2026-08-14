# 任务：把 DockQ 原生集成到 AlphaFold 2 预测流程

工作目录 `/testbed` 是锁定在 commit
`c77e5d2a8961d1a353632c462914ff0a32a950f6` 的 AlphaFold 2 源码。请在其中实现
DockQ 二链蛋白复合物评分，并让 AlphaFold 的标准预测流程默认产出该评估结果。
这是一道算法迁移题：仅增加一个独立包装脚本不算完成。

## 可用研究材料与提交边界

- 锁定的 DockQ commit `75db7ab4f6b824c70d120c5f620582e164ed5479`
  的源码、README 和 MIT 许可证位于 `/opt/dockq`；允许在做题时阅读和运行。
- 5 个公开输入/输出样例位于 `/examples`，可运行
  `python3 /examples/verify_examples.py /testbed/alphafold/common/dockq_score.py`
  做快速检查。
- Agent 环境全程断网，不提供 GPU、模型参数或完整数据库，因此解题阶段不需要运行
  神经网络。独立 verifier 内置一份锁定的 multimer 权重，并会在 H200 上运行一个
  有界的真实端到端推理；Agent 无法读取 verifier 私有的权重、输入或参考结果。
- 最终提交是 `/testbed`。不得把 `/opt/dockq` 复制进提交，不得安装、导入、调用、
  链接或以子进程执行 DockQ，也不得读取预生成答案表。提交必须只依赖 AlphaFold
  已有依赖，在没有 DockQ 包、源码、可执行文件和网络的环境中运行。

只允许修改 `run_alphafold.py`，并新增
`alphafold/common/dockq_score.py`；删除或修改其他锁定的 AlphaFold 文件会触发回归门禁。

## 1. 原生评分接口

在 `alphafold/common/dockq_score.py` 实现：

```python
score_complex(
    model,
    native,
    mapping=None,
    contact_cutoff=5.0,
    interface_cutoff=10.0,
) -> dict
```

`model` 与 `native` 均为内存字典：

```python
{
  "chains": {
    "A": [
      {"name": "ALA", "atoms": {"N": [x, y, z], "CA": [x, y, z], ...}},
      ...
    ],
    "B": [...]
  }
}
```

本题范围固定为两个蛋白链；映射后的链序列完全相同，残基一一对应。实现须计算：

- native residue contacts 的保留比例 `fnat`；
- native 界面残基主链原子的 Kabsch `iRMSD`；
- 受体对齐后的 ligand `LRMSD`；
- 连续 DockQ 分数及 CAPRI 标签；
- native/preserved contact 数量。

未提供 `mapping` 时，搜索所有序列兼容的链映射并返回 DockQ 最大者；返回的
`mapping` 方向必须是 `model_chain_id -> native_chain_id`。结果必须恰好包含：

```text
fnat, iRMSD, LRMSD, DockQ, CAPRI,
native_contacts, preserved_contacts, mapping
```

同一文件还必须提供 CLI：

```bash
python3 alphafold/common/dockq_score.py \
  --model MODEL.json --native NATIVE.json --output RESULT.json
```

JSON 必须是标准 JSON，不能出现 `NaN` 或 `Infinity`。所有浮点字段按相对或绝对
误差 `5e-4` 验收。

## 2. 接入 AlphaFold 标准预测流程

修改 `run_alphafold.py`：

- 增加字符串 flag `--dockq_native_path`，接收参考结构 PDB；
- 增加默认值为 `true` 的布尔 flag `--run_dockq`；
- 给 `predict_structure(...)` 增加向后兼容的尾部关键字参数：

```python
dockq_native_path: Optional[str] = None
run_dockq: bool = True
```

行为要求：

- `run_dockq=true` 且提供 native PDB：对每个预测模型自动评分；
- 未提供 native：明确记录 `not_computed`，不得用 pLDDT、ipTM 等置信度冒充 DockQ；
- `run_dockq=false`：不得解析 native，明确记录 `disabled`；
- 单个评分失败：保存该模型与其他模型原有预测产物，记录可诊断的 `error`；所有
  可保存的后处理完成后，以非零状态报告本次任务存在评分错误。

评分对象是每个模型刚生成的 **unrelaxed structure**（即写入对应
`unrelaxed_<model_name>.pdb` 的同一坐标），不是随后可能经过 Amber relax 的结构。

每个 `result_<model_name>.pkl` 新增 `dockq_evaluation`。同一 FASTA 的标准输出目录
还要生成 `dockq_scores.json`，顶层键是模型名，其值必须与对应 pkl 中的记录完全一致。
无论状态为何，每条记录必须恰好具有统一 schema：

```text
status, reason, dockq, fnat, irms, lrms, capri,
native_contacts, preserved_contacts, mapping
```

各状态取值：

| 情况 | `status` | `reason` | 其他字段 |
|---|---|---|---|
| 成功 | `computed` | `null` | 原生评分结果 |
| 无 native | `not_computed` | `native_structure_not_provided` | 全部 `null` |
| 用户关闭 | `disabled` | `disabled_by_user` | 全部 `null` |
| 评分异常 | `error` | 非空诊断文本 | 全部 `null` |

这里的“默认评分”是指标准预测结果始终携带评估状态；只有提供参考结构时才可能产生
真实 DockQ 数值。

## 3. 隐藏验收与评分

评分使用独立、断网的 verifier 容器：DockQ 不存在于候选运行环境，且候选以无特权
用户运行，无法读取 reference、隐藏期望值或评分文件。Verifier 先用锁定的原始
DockQ 动态生成参考结果，随后移除 donor，再运行候选实现。

硬门禁包括：源码不能导入/调用/vendor DockQ 或其他外部运行时、接口可加载、锁定
AlphaFold 文件未被破坏，以及原有输出行为的快速回归检查。快速回归使用受控的小型
fixture，但不作为真实端到端用例计分，也不能替代下面的 H200 推理。

其余分数为 15 个隐藏用例的通过率：1～9 为 DockQ 数值差分，10 为独立 CLI，11 为
AlphaFold flags/签名/传参契约，12～15 共享一次真实的修改版 AF2 multimer 推理，分别
验证官方 `DataPipeline` 与 `RunModel`/H200、原版与修改版预测等效、集成 DockQ 与锁定
原始 DockQ 等效、以及标准 PDB/PKL/JSON 产物保持完整。正式的 12～15 不使用
`FakeRunner` 或 `FakeDataPipeline`。

真实用例固定单模型 `model_1_multimer_v3`、一个随机种子和一次 recycle；MSA 使用官方
支持的 query-only 预计算输入，模板搜索真实执行 `hmmbuild+hmmsearch`，并由官方重复
命中过滤器防止模板泄漏。该配置用于验证真实集成链路，不声称具有生产级数据库下的
预测质量。比如通过 12/15，得分为 0.8。
