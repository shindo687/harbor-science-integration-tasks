# Implement a native Markov-state-model analysis in OpenMM

Work only in `/testbed`, which contains the locked OpenMM source tree.  Add
`wrappers/python/openmm/app/markov_model.py` and publicly export
`estimate_markov_model` from `wrappers/python/openmm/app/__init__.py`.

Your implementation must be clean-room OpenMM code.  It must not import,
execute, link, download, or vendor PyEMMA, deeptime, msmtools, or another MSM
implementation.  The final verifier has no network and removes the locked
reference implementation before running your code.

## Required API

```python
estimate_markov_model(
    trajectories,
    lag=1,
    count_mode="sliding",
    reversible=True,
    connectivity="largest",
)
```

Return a `dict` with these keys:

- `active_set`: sorted original state labels retained in the model
- `count_matrix`: transition counts on `active_set`
- `transition_matrix`: row-stochastic maximum-likelihood transition matrix
- `stationary_distribution`: stationary probabilities on `active_set`
- `eigenvalues`: JSON-friendly `[real, imag]` pairs, with the stationary
  eigenvalue first and the rest sorted by decreasing magnitude
- `timescales`: `-lag/log(abs(lambda))` for non-stationary eigenvalues; use
  JSON-compatible `None` when the implied timescale is not finite

## Bounded semantics

- `trajectories` is either one integer sequence or a non-empty sequence of
  integer sequences.  Labels are non-negative integers.
- `lag` is a positive integer.
- `count_mode="sliding"` counts every pair `(x[t], x[t+lag])`.
- `count_mode="sample"` counts pairs starting at `t = 0, lag, 2*lag, ...`.
- `connectivity="largest"` retains the largest connected component of the
  observed count graph.  Break equal-size ties by the smallest state label.
- In reversible mode, estimate the reversible maximum-likelihood transition
  matrix, not a simple symmetrization.  In non-reversible mode, row-normalize
  the directed counts.
- Reject malformed input with `TypeError` or `ValueError`.

The verifier uses public and hidden fixtures and also checks stochasticity,
stationarity, and detailed balance.  Preserve existing OpenMM behavior and do
not make unrelated changes.
