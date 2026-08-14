# Task: implement OpenMM's native bounded MBAR estimator

The working tree at `/testbed` is the locked OpenMM source at commit
`c6173db6e8edd705eb59172bd21e9ce69c572405`. Implement a clean-room MBAR
analysis module in OpenMM's Python application layer. This is an algorithm
migration task: wrapping pymbar, copying its implementation, or returning
precomputed answers is not an implementation.

## Research material and submission boundary

- Locked pymbar commit `ed40ec3bbef03bb08938ad1a74d459b0d1ab81f7` and its
  MIT license are available for study at `/opt/pymbar-source`.
- Five public examples will be available at `/examples`.
- The environment is offline. Only `/testbed` is submitted to the separate
  verifier; donor source and examples never cross that boundary.
- The final implementation must not import, execute, link, install, download,
  or vendor pymbar. NumPy and the Python standard library are available.

## Bounded scientific scope

Given a finite `K x N` reduced-potential matrix `u_kn` and integer sample
counts `N_k`, implement numerically stable multistate Bennett acceptance ratio
estimation with:

- a self-consistent or Newton/root solve with `f_k[0] == 0` gauge fixing;
- log-sum-exp handling of extreme reduced potentials;
- normalized MBAR weights and the state-overlap matrix;
- asymptotic covariance/free-energy-difference uncertainty;
- per-state effective sample number and convergence diagnostics;
- explicit validation of shapes, counts, finite values, tolerances, and empty
  sampled states. Timeseries subsampling, observables, bootstrap, and FES are
  out of scope.

## Required OpenMM API

Add `wrappers/python/openmm/app/mbar.py` and export `estimate_mbar` from
`wrappers/python/openmm/app/__init__.py`:

```python
estimate_mbar(
    u_kn,
    N_k,
    *,
    initial_f_k=None,
    relative_tolerance=1e-10,
    maximum_iterations=10000,
) -> dict
```

The returned dictionary must contain NumPy-compatible values under:

```text
f_k, Delta_f, dDelta_f, covariance, weights, overlap,
effective_sample_number, iterations, residual, converged
```

`weights` has shape `(N, K)` and each thermodynamic-state column sums to one.
`overlap` is the standard MBAR overlap matrix. Free energies are dimensionless.

## Differential scoring

The separate offline verifier generates fresh reduced potentials using locked
OpenMM systems, evaluates the same matrices with locked pymbar, destroys all
private reference material, and only then executes the candidate as an
unprivileged user. Hidden cases cover two-state high/low overlap, a three-state
bridge, unequal counts, duplicated samples, unsampled states, extreme energy
offsets, analytic oscillators, warm starts, and invalid inputs.

The verifier compares gauge-fixed free energies and differences at `1e-8`,
covariance/uncertainty and effective sample numbers at bounded numerical
tolerances, and checks antisymmetry, path additivity, normalized weights,
row-stochastic overlap, common sample-offset invariance, and deterministic
results. A failed API/import gate, donor use or vendoring, source-provenance
failure, changes outside the allowed OpenMM integration surface, or failed
host regressions gives zero. Otherwise reward is the fraction of 15 hidden
points passed.

