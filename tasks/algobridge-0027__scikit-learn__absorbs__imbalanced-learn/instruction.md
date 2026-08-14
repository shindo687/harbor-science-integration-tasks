# scikit-learn 原生 deterministic SMOTE

在 `/testbed` 的锁定 scikit-learn 源码中实现 classic SMOTE，使以下接口可用：

```python
from sklearn.preprocessing import SMOTE

sampler = SMOTE(
    sampling_strategy="auto",
    k_neighbors=5,
    random_state=42,
)
X_resampled, y_resampled = sampler.fit_resample(
    X, y, sample_weight=sample_weight,
)
```

只能修改 `/testbed`。`/opt/imbalanced-learn` 提供锁定 donor 源码和文档供研究；最终 Candidate 不得 import、调用、链接、下载或 vendor imbalanced-learn，也不得复制 donor 实现。

## 受限算法范围

- dense、有限、连续数值特征；binary 或 multiclass 一维标签；
- exact Euclidean kNN；`k_neighbors` 为正整数；
- 支持 imbalanced-learn classic SMOTE 的 `"auto"`、`"minority"`、`"not minority"`、`"not majority"`、`"all"`、目标计数字典，以及 binary `(0, 1]` float ratio；
- 使用 scikit-learn/NumPy 的 legacy integer-seeded RNG 语义；固定 seed 时应与锁定 donor 逐元素一致；
- 不含 categorical、Borderline/SVM SMOTE、近似近邻或稀疏输入。

对每个目标类别，结果必须把原始 `X/y` 原样放在前缀，随后按类别排序追加 synthetic rows。等距近邻沿用锁定 scikit-learn exact kNN 的索引顺序。

## 结果与 fitted attributes

`fit_resample` 返回 `(X_resampled, y_resampled)`，并设置：

- `sampling_strategy_`：`class -> 本次生成数`；
- `parent_indices_`：形状 `(n_synthetic, 2)`，每行是 parent 与 selected same-class neighbor 在原始输入中的行号；
- `lambdas_`：形状 `(n_synthetic,)`，满足 `x_new = x_parent + lambda * (x_neighbor - x_parent)`；
- `sample_weight_resampled_`：未提供 `sample_weight` 时为 `None`；否则保留原始权重，并用同一 lambda 在线段两端权重之间插值生成 synthetic 权重。

还应设置常规的 `n_features_in_`。输入、策略、标签或 `k_neighbors` 不合法时必须明确拒绝。

## 验收

Verifier 动态运行锁定的原始 scikit-learn → imbalanced-learn pipeline，然后删除 donor、reference venv、源码和 wheelhouse，再以无特权用户运行修改后的 scikit-learn。隐藏测试比较：

- `X/y` 及 dtype/shape；synthetic 数值绝对容差 `1e-12`；
- parent/neighbor/lambda provenance；
- sample-weight lineage；
- 线段、目标类别计数、原始多数类/输入前缀、确定性与 tie 行为；
- scikit-learn 宿主回归测试。

Agent 环境中可运行：

```bash
/opt/task-tools/run-public-examples
```
