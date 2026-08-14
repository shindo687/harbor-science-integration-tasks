# Task: native exact TreeSHAP in scikit-learn

Work in the scikit-learn source tree at `/testbed`. Add a public
`sklearn.inspection.tree_shap` function that computes exact, path-dependent
TreeSHAP values for fitted scikit-learn numeric binary trees.

## Required API

```python
from sklearn.inspection import tree_shap

result = tree_shap(estimator, X, *, output=None, check_additivity=True)
result["values"]
result["base_values"]
result["predictions"]
```

Return a `sklearn.utils.Bunch` with these keys (use mapping access for
`"values"`, because `Bunch.values` is also the standard dictionary method):

- `values`: `(n_samples, n_features)` for one raw output, otherwise
  `(n_samples, n_features, n_outputs)`.
- `base_values`: a scalar for one raw output, otherwise `(n_outputs,)`.
- `predictions`: `(n_samples,)` for one raw output, otherwise
  `(n_samples, n_outputs)`.

When `output` selects one output, return the single-output shapes. It accepts an
integer output index; for classifiers it also accepts a value from `classes_`.
Reject an invalid selector. `X` may be a dense array or a pandas DataFrame and
must follow normal sklearn feature validation.

## Supported estimators and raw-output meaning

- `DecisionTreeRegressor`, including multi-output: `predict`.
- `RandomForestRegressor`, including multi-output: `predict`.
- `GradientBoostingRegressor`: `predict`.
- `DecisionTreeClassifier` and `RandomForestClassifier`, binary or multiclass:
  `predict_proba`.
- Binary `GradientBoostingClassifier`: `decision_function` (log odds).

The estimator must be fitted. Support numeric binary splits, repeated features
and thresholds, sample weights, and sklearn's learned missing-value direction.
Categorical splits, sparse input, multiclass GradientBoostingClassifier,
interaction values, interventional backgrounds, GPU execution, and
multi-output classification are outside scope and should fail clearly.

## Exactness and invariants

Implement the path-probability dynamic program for exact
`tree_path_dependent` TreeSHAP. Node cover values from the fitted tree define
the background distribution. Ensemble contributions must use the model's exact
tree scaling and initial raw value.

For every supported result:

```text
base_values + values.sum(feature_axis) == predictions
```

within floating-point roundoff. Features unused by all splits have exactly zero
attribution. Tree aggregation must be deterministic and preserve estimator
order.

## Integration requirements

- Export `tree_shap` from `sklearn.inspection` and add focused sklearn tests and
  API documentation/docstrings. The focused test module must be named
  `sklearn/inspection/tests/test_tree_shap.py`.
- Preserve existing scikit-learn behavior and tests.
- Do not import, call, link, download, or vendor SHAP at runtime.
- Do not inspect verifier files or embed expected fixture outputs.
- Network access is disabled. Relevant locked SHAP source is available at
  `/opt/shap-source` for algorithm study; public examples are in `/examples`.
- Run `/opt/task-tools/run-public-examples` while developing.

The verifier independently trains fresh locked scikit-learn models, computes
reference values with the locked SHAP `TreeExplainer`, removes that reference
runtime, and then runs the modified scikit-learn implementation as an
unprivileged user. Numeric `base_values` and `values` are compared at absolute
and relative tolerance `1e-9`; shapes, raw predictions, local accuracy, unused
features, dependency isolation, and representative upstream regressions are
also checked.
