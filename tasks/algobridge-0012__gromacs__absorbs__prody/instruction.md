# Implement native anisotropic-network analysis in GROMACS

Work only in `/testbed`, which contains the locked GROMACS source tree. Add
these two files and do not modify or remove existing host files:

```text
python_packaging/gmxapi/src/gmxapi/analysis/__init__.py
python_packaging/gmxapi/src/gmxapi/analysis/anm.py
```

The implementation must be independent GROMACS/gmxapi source. It must not
import, execute, link, download, or vendor ProDy or another elastic-network
implementation. The final candidate environment has no network and physically
removes the reference runtime and donor source before candidate execution.

## Required API

Export `analyze_anm` from both files:

```python
analyze_anm(
    coordinates_nm,
    *,
    selection=None,
    cutoff_nm=1.5,
    gamma=1.0,
    n_modes=20,
) -> dict
```

`coordinates_nm` is a finite numeric `(N, 3)` array in GROMACS nanometers.
`selection` is `None` or a one-dimensional, non-empty sequence of unique
zero-based atom indices; its order is the output node order. The bounded task
uses 4--64 selected C-alpha nodes. Reject duplicate selected coordinates,
malformed indices, non-finite data, `cutoff_nm < 0.4`, non-positive `gamma`,
and non-positive/non-integer `n_modes` with `TypeError` or `ValueError`.

Return:

- `node_indices`: selected source indices in order;
- `hessian`: the full `(3M, 3M)` ANM Hessian;
- `zero_mode_count`: number of Hessian eigenvalues below `1e-6`;
- `component_count`: number of connected components in the cutoff graph;
- `eigenvalues`: the lowest requested eigenvalues at least `1e-6`;
- `modes`: corresponding normalized eigenvectors as columns `(3M, K)`;
- `covariance`: `modes @ diag(1/eigenvalues) @ modes.T`;
- `msf`: trace of each diagonal `3x3` covariance block;
- `cross_correlation`: normalized trace of every node-pair covariance block.

If fewer than `n_modes` positive modes exist, return every available positive
mode. Reject a network with no positive modes.

## Numerical semantics

For each distinct selected node pair within the inclusive cutoff, let
`r = x_j - x_i` and

```text
B = -gamma * outer(r, r) / dot(r, r)
H_ij = H_ji = B
H_ii -= B
H_jj -= B
```

Pairs outside the cutoff contribute zero. Diagonalize the symmetric Hessian,
sort modes by ascending eigenvalue, and use exactly the `1e-6` zero-mode
threshold above. Do not multiply covariance or MSF by a temperature or
Boltzmann factor. The real reference converts nanometers to angstroms, applies
the identical ordered selection, and calls the locked ProDy `ANM.buildHessian`
and `ANM.calcModes` pipeline.

The verifier compares Hessian/eigenvalues, degenerate eigenspace projectors,
covariance, MSF, cross-correlation, mapping and diagnostics. It also checks
Hessian symmetry/block row sums, positive semidefiniteness, rigid-transform,
atom-reordering, gamma-scaling, component/zero-mode behavior, covariance
reconstruction and invalid inputs. Hidden fixtures cover linear, planar,
three-dimensional, disconnected, cutoff-boundary and degenerate networks.

After implementing the API, run `/opt/task-tools/run-public-examples` to replay
all five public fixtures against your `/testbed` source tree.
