# Public examples

Run `/opt/task-tools/run-public-examples` inside the Agent environment after
implementing `scipy.stats.robust_linear_model`.

The five visible cases cover a clean fit, a strong outlier, no intercept,
integer frequency weights, all three covariance estimators, and Huber proposal
2 scale. `expected.json` is frozen from the locked original SciPy +
statsmodels reference pipeline; hidden fixtures are separate.

