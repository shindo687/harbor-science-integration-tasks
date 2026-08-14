# Implement native third-order force-constant fitting in phonopy

Work only in `/testbed`, which contains the locked phonopy source tree.  Add
`phonopy/harmonic/third_order.py` with the API below.  Preserve existing
phonopy behavior and do not make unrelated changes.

Your implementation must be independent phonopy code.  It must not import,
execute, link, download, or vendor phono3py, symfc, or another FC3
implementation.  The final verifier has no network and physically removes the
reference runtime before candidate execution.

## Required API

```python
fit_fc3(
    supercell,
    displacements,
    forces,
    *,
    is_symmetry=True,
    symprec=1e-5,
) -> dict
```

`supercell` is a `phonopy.structure.atoms.PhonopyAtoms`.  `displacements` and
`forces` are finite arrays with identical shape `(n_snapshots, n_atoms, 3)`.
The bounded task uses 2--4 atoms and at least two snapshots.  `is_symmetry`
selects whether phonopy's crystallographic operations are imposed; `symprec`
is a finite positive symmetry tolerance.

Return a dictionary containing:

- `fc2`: full `(N, N, 3, 3)` harmonic force constants;
- `fc3`: full `(N, N, N, 3, 3, 3)` third-order force constants;
- `predicted_forces`: forces reconstructed at the input displacements;
- `residual_norm`: Euclidean norm of `predicted_forces - forces`;
- `rank`: numerical rank of the constrained joint FC2/FC3 design;
- `singular_values`: descending singular values of that design;
- `condition_number`: largest divided by smallest retained singular value;
- `n_parameters`: number of pair-plus-triple polynomial coefficients before
  crystallographic augmentation;
- `symmetry_operation_count`: number of operations used in the fit.

## Bounded numerical semantics

Use the potential expansion whose force convention is

```text
F[i,a] = - sum(j,b) FC2[i,j,a,b] u[j,b]
         - 1/2 sum(j,k,b,c) FC3[i,j,k,a,b,c] u[j,b] u[k,c].
```

- Fit FC2 and FC3 jointly by ordinary least squares with relative cutoff
  `rcond=1e-12`.
- Enforce derivative-index permutation symmetry, e.g. swapping `(i,a)` with
  `(j,b)` does not change FC3.
- Enforce translational acoustic sum rules on every atomic index.  A valid
  clean-room parameterization is the lexicographically ordered quadratic and
  cubic monomials of each atom's Cartesian displacement relative to the final
  atom.
- When `is_symmetry=True`, use phonopy's space-group rotations and atomic
  permutations to augment equivalent displacement/force observations before
  the least-squares solve.  Cartesian vectors rotate with the
  lattice-transformed operation.
- Report rank using singular values greater than `1e-12 * largest`; report the
  condition number over retained singular values.  Reject a zero-rank design.
- Reject malformed input with `TypeError` or `ValueError`.

The real reference constructs the same phonopy structure and calls the locked
phono3py `Phono3py.produce_fc3(fc_calculator="symfc",
is_compact_fc=False)`.  Public examples cover P1 and crystallographic fits.
After implementing the API, run `/opt/task-tools/run-public-examples` to replay
all five public fixtures against your `/testbed` source tree.
Hidden tests additionally cover two/three/four-atom cells, redundant/noisy
forces, a symmetry-resolved underdetermined dataset, high-symmetry crystals,
atom reordering, rigid rotation, acoustic force drift, and invalid inputs.
