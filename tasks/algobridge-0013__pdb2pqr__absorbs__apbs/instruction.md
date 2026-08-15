# Add a bounded uniform-grid LPBE solver to PDB2PQR

Work in `/testbed`, a complete locked PDB2PQR 3.7.1 source tree. A complete
APBS 3.4.1 source tree is available for documentation at `/opt/donor-source`.
Implement the bounded downstream capability inside PDB2PQR; the final solution
must not invoke, import, bundle, or depend on APBS.

Add exactly one UTF-8 Python source file:

```text
pdb2pqr/lpbe_grid.py
```

Do not modify or remove existing PDB2PQR files. The module may import only
NumPy, the standard-library `math` module, and optional `__future__` features.

## Required API

```python
solve_lpbe(packet)
```

The packet is the bounded uniform-grid kernel boundary after PQR parsing and
APBS dielectric, accessibility, charge, and Debye-Hückel boundary-map
construction. Solve the linearized Poisson-Boltzmann equation with a
matrix-free preconditioned conjugate-gradient method. Do not return fixtures or
hard-code the disclosed grids.

Packet schema `algobridge-pdb2pqr-lpbe-grid-v1` has:

- `dims`: three odd grid dimensions in `[5, 65]`; arrays are flat in
  `i * ny * nz + j * nz + k` order.
- `spacing`: positive x/y/z grid spacing in angstrom.
- positive finite `temperature` and `zmagic`, and nonnegative finite
  `zkappa2`.
- `diel_x`, `diel_y`, `diel_z`: positive finite face-dielectric maps.
  At cell `(i,j,k)`, each value weights its positive-axis face; the preceding
  grid entry weights the negative-axis face.
- `kappa`: finite solvent-accessibility values in `[0,1]` for the screened
  reaction term.
- `charge`: finite APBS charge-density map.
- `boundary`: finite potential map; its six boundary faces are prescribed
  Dirichlet values.
- `relative_tolerance` in `[1e-14,1e-4]` and `max_iterations` in `[1,20000]`.

The finite-volume row uses face dielectric times transverse area divided by
normal spacing. Its diagonal is the six face weights plus
`zkappa2 * kappa * cell_volume`; its source is
`zmagic * charge * cell_volume`, with prescribed boundary-neighbor terms moved
to the right-hand side.

## Return value

Return exactly:

- `schema="algobridge-pdb2pqr-lpbe-result-v1"` and the input `dims`.
- `potential`: the complete finite flat grid, including prescribed boundary
  values.
- `energy_kj_mol`: `0.5 * sum(charge * potential) * cell_volume * kB * T *
  NA / 1000`, with `kB=1.3806581e-23` and `NA=6.0221367e23`.
- `diagnostics`: `converged`, `iterations`, independently recomputable
  `absolute_residual`, `relative_residual`, and a finite nonnegative
  `residual_history`.

Raise an exception for malformed packets or failure to converge.

## Validation

Five disclosed APBS-derived packets and native results are in `/examples`:

```bash
/opt/task-tools/run-public-examples
```

The separate no-network verifier runs official APBS 3.4.1 as a root-only
reference on fifteen additional molecular systems. Potential max absolute error
must be at most `1e-4`; energy error must be at most `max(0.02 kJ/mol, 2e-4
relative)`. It also checks an independent linear residual, boundary values,
energy self-consistency, invalid inputs, metamorphic identities, source
integrity, provenance, and candidate/reference isolation. Hidden reward is the
fraction of scientific cases passed; hard-gate failures earn zero.
