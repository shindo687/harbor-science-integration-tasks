# ALGOBRIDGE-0025：scikit-learn 原生二阶精确提升树

状态：`accepted`。这是一道 CPU-only、离线、single-step Harbor 算法迁移题：
要求 Agent 在锁定 scikit-learn 中实现 bounded
`SecondOrderGradientBoosting`，候选执行时不得调用、import、链接或 vendor
XGBoost、LightGBM、CatBoost 等现成提升树实现。

## 能力边界与真实差分

锁定 scikit-learn 已有传统 exact gradient boosting 和 histogram gradient
boosting，但没有同时提供 XGBoost exact greedy Hessian gain、L1/L2 叶正则、
逐 split missing default direction 与 row weight 语义的公共 estimator。因此本题
不是给现有类增加别名。

```text
scikit-learn dense X/y/weights → 锁定 XGBoost exact CPU → 参考结果
                                                            │
修改后的 sklearn.ensemble → SecondOrderGradientBoosting     ├─ 差分比较
                                                            │
                  数学不变量与隔离门禁 ──────────────────────┘
```

Agent 只能修改：

```text
sklearn/ensemble/__init__.py
sklearn/ensemble/_second_order_gradient_boosting.py
```

支持 4--256 行、1--16 个 dense numeric features、NaN missing、平方误差/二元
logistic、depth 1--3、1--12 棵树、L1/L2/gamma、positive row weights 和
`learning_rate` 0--1。完整 sklearn 风格 API、树 schema 和非法输入约定见
`instruction.md`。

源码被精确固定为：

- scikit-learn `e27ccf58592fcfe8c7ca87f53dde840c436093b2`；
- XGBoost `a3e3df59b83e1f230bb238c99dbaf63d8382ed24`，版本
  `3.5.0-dev`，dmlc-core 子模块也固定；
- `python:3.12.11-bookworm`，使用镜像 digest 固定；
- XGBoost reference 是从上述 commit 构建的 12 MB CPU-only shared library，
  禁用 CUDA、NCCL 和 OpenMP。

源码 archive、tree、reference library、wheel manifest 和基础镜像 SHA256 位于
`source-lock.json`；许可证边界见 `THIRD_PARTY.md`。Docker build 内所有 Python
依赖均来自仓库内 wheels，使用 `--no-index`，不下载依赖。

## Agent / verifier 隔离

`task.toml` 使用 `environment_mode = "separate"` 和 `network_mode =
"no-network"`。Agent 获得完整 scikit-learn 源码、仅作开发参考的 XGBoost 源码/文档、
NumPy/SciPy 与已构建的锁定 sklearn；它没有 XGBoost runtime。

Verifier 在新的容器中：

1. 校验 reference shared library SHA256；
2. 比较 `/testbed` 与 pristine host，只允许上述两个 Python 文件发生变化；
3. 检查禁止依赖/执行原语和 64/96-token donor 片段；
4. 用真实锁定 XGBoost `tree_method="exact"`、`nthread=1` 计算 15 组参考结果；
5. 把两个候选文件 overlay 到锁定 sklearn wheel runtime；
6. 物理删除 XGBoost runtime/source、reference runner、wheels 和 pristine host；
7. 将 `/testbed` 与候选 runtime 设为只读，以 UID/GID 10001、无网络运行候选；
8. 检查 9 个非法输入、宿主回归与跨用例不变量，然后逐例差分评分。

逐例比较规范化 tree topology、feature、threshold、default direction、leaf、
cover、gain、raw margin、predict/proba、feature total gain 与 loss history。
核心 threshold/leaf/margin 使用约 `2e-7` 容差；gain 允许锁定 JSON decimal dump
的数个 float32 ulp。另行检查：

- weighted training loss 每轮不增加；
- `learning_rate=0` 时 margin 保持 0；
- 训练行重排后规范化模型与对齐预测不变；
- NaN 遵循树中记录的 default branch；
- L1 可产生精确零叶；
- child cover 之和等于 parent cover，feature gain 可由树重建。

任何硬门禁失败直接得 0，否则 Reward 为通过数除以 15。

## 验收结果

| 实现 | 结果 | Reward |
|---|---:|---:|
| clean-room Oracle | 15/15 | 1.0 |
| pristine scikit-learn（NOP） | source gate | 0.0 |
| 错误地把 Hessian 加倍的 near miss | 0/15 | 0.0 |
| 直接 import XGBoost | dependency gate | 0.0 |
| 公开样例 | 5/5 | — |

公开 fixture 仅由锁定 XGBoost reference 生成；重新生成逐字节一致。Agent 实现
API 后可在无 donor runtime 的环境中回放：

```bash
/opt/task-tools/run-public-examples
```

## 使用 Harbor

```bash
harbor run --path . --agent oracle --job-name algobridge-0025-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0025-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

需要 Linux x86_64、Docker/兼容后端、约 16 GB 内存和 20 GB 临时存储；不需要
GPU 或 H200。基础镜像首次获取可能需要联网，但镜像构建中的依赖安装、Agent 与
verifier 运行都只使用仓库内锁定材料且禁止联网。
