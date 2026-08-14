## Task

Work in the locked scikit-learn source tree at `/testbed`. Add a bounded exact
second-order gradient-boosted tree estimator without using XGBoost at runtime.

You may change only:

```text
sklearn/ensemble/__init__.py
sklearn/ensemble/_second_order_gradient_boosting.py
```

Export this class from `sklearn.ensemble`:

```python
SecondOrderGradientBoosting(
    *,
    objective="squared_error",
    n_estimators=6,
    max_depth=2,
    learning_rate=0.3,
    reg_lambda=1.0,
    reg_alpha=0.0,
    min_split_loss=0.0,
)
```

The estimator must implement:

```python
fit(X, y, sample_weight=None) -> self
decision_function(X) -> ndarray of raw margins
predict(X) -> ndarray
predict_proba(X) -> ndarray of shape (n_samples, 2)  # logistic only
```

After `fit`, provide:

```text
trees_             list of normalized nested tree dictionaries
feature_gains_     float array of length n_features (total split gain)
training_loss_     float array containing the initial loss and one value per tree
n_features_in_     input feature count
```

Each split dictionary has exactly these semantic fields (additional harmless
fields are allowed):

```text
node_id, depth, feature, threshold, missing, gain, cover, left, right
```

`missing` is the string `"left"` or `"right"`. Each leaf dictionary has
`node_id`, `depth`, `leaf`, and `cover`. Leaf values already include
`learning_rate`, as in the locked reference dump.

## Bounded numerical contract

- dense numeric `X`, 4--256 rows and 1--16 columns;
- finite values or `NaN` (missing); infinities are invalid;
- `objective` is `"squared_error"` or `"logistic"`;
- regression targets are finite; logistic targets are exactly 0 or 1;
- optional `sample_weight` is finite and strictly positive;
- `1 <= n_estimators <= 12`, `1 <= max_depth <= 3`;
- `0 <= learning_rate <= 1` and all three regularizers are non-negative;
- regression starts at raw margin 0; logistic starts at probability 0.5,
  hence raw margin 0;
- exact split enumeration, depth-wise growth, and XGBoost-compatible L1/L2
  leaf weights, split gain, missing default direction, and pruning are required;
- deterministic ties are resolved by the locked exact reference.

For regression, `predict` equals the raw margin. For logistic classification,
`decision_function` returns the raw logit, `predict_proba` applies the stable
sigmoid, and `predict` thresholds positive-class probability at 0.5.
`training_loss_` uses weighted mean half-squared error for regression and
weighted mean binary log loss for logistic classification.

Reject invalid inputs with `ValueError` before fitting.

## Differential verification

The private verifier runs the same input through locked XGBoost
`a3e3df59b83e1f230bb238c99dbaf63d8382ed24` with
`tree_method="exact"`, `nthread=1`, and fixed deterministic parameters, then
runs only the modified scikit-learn after physically removing the XGBoost
runtime and donor source.

It compares normalized tree structure, thresholds, leaves, covers and gains;
raw margins, predictions/probabilities, feature gains, and loss history. It
also checks at least these invariants:

- every boosting stage has non-increasing weighted training loss;
- `learning_rate=0` leaves all raw margins at zero;
- permuting training rows does not change the normalized model or aligned
  predictions;
- missing rows follow the recorded default branch;
- L1 regularization can produce an exactly zero leaf.

Do not import/call/link XGBoost or another boosted-tree implementation, launch
subprocesses, access the network, or copy donor implementation code.

