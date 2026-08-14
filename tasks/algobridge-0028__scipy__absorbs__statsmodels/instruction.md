## Task

Implement native Huber robust linear regression in the SciPy source tree at
`/testbed`.

Add the public function `scipy.stats.robust_linear_model`.  It must reproduce
the bounded behavior of the locked statsmodels `RLM(..., M=HuberT(...)).fit`
pipeline without importing, invoking, linking, downloading, or vendoring
statsmodels at candidate runtime.

### Public interface

```python
scipy.stats.robust_linear_model(
    x,
    y,
    *,
    fit_intercept=True,
    huber_t=1.345,
    scale="mad",
    covariance="H1",
    case_weights=None,
    tol=1e-8,
    maxiter=50,
)
```

The returned object must expose these attributes:

- `params`: coefficients, with the intercept first when requested;
- `scale`: final robust scale;
- `weights`: final Huber weights, one per original observation;
- `covariance`: robust H1, H2, or H3 covariance matrix;
- `residuals`: residuals, one per original observation;
- `history`: a mapping containing finite `objective`, `scale`, and `params`
  histories (the initial OLS fit is included);
- `n_iter` and `converged`.

Supported scale estimators are `"mad"` and `"huber"` (Huber proposal 2 with
the locked donor defaults). `case_weights` are bounded positive integer
frequency weights: a weight of `k` has exactly the semantics of repeating the
row `k` times. Returned residuals and weights are collapsed back to the
original rows.

Inputs are finite real-valued dense arrays. `x` is two-dimensional and `y` is
one-dimensional. The number of effective observations must exceed the design
rank. `huber_t`, `tol`, and `maxiter` must be positive. Other M-estimators,
missing-value handling, formulas, and sparse inputs are outside this task.

### Required numerical behavior

The verifier dynamically runs the same arrays through the original locked
SciPy + statsmodels pipeline and compares:

- parameters, scale, robust weights, residuals, and finite objective history:
  absolute/relative tolerance `1e-8`;
- robust covariance: absolute/relative tolerance `1e-6`.

It covers intercept/no-intercept fits, MAD and Huber scale, H1/H2/H3
covariance, strong outliers, high leverage, frequency weights, rank-deficient
designs, alternate Huber thresholds, and near-zero scale.

The implementation must also satisfy the Huber estimating equation, response
unit equivariance, and agreement with ordinary least squares on clean data.
Preserve SciPy's existing public behavior and tests.

### Development material

- `/testbed`: locked SciPy source;
- `/opt/statsmodels-source`: locked donor source and documentation for study;
- `/examples`: public cases, frozen expected results, and an offline checker;
- `/opt/task-tools/materialize_candidate.py`: refresh the installed SciPy
  extension modules beneath the editable source tree when needed.

The candidate verifier has no statsmodels installation or donor source, runs
without a network as an unprivileged user, and rejects source/binary delegation.

