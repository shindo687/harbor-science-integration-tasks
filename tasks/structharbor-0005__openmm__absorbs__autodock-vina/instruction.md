# Add native Vina fixed-pose scoring to OpenMM

Work in `/testbed`, a complete locked OpenMM 8.4.0 source tree. A complete
AutoDock Vina 1.2.7 source tree is available for documentation at
`/opt/donor-source`. Implement the bounded downstream capability inside OpenMM;
the final solution must not invoke, import, bundle, or depend on AutoDock Vina.

Add exactly one UTF-8 Python source file:

```text
wrappers/python/openmm/app/vina_score.py
```

Do not modify or remove any existing OpenMM file. The module must use only the
Python standard-library `math` module (plus an optional `__future__` import).

## Required API

```python
score_vina_pose(
    receptor_types,
    receptor_positions,
    ligand_types,
    ligand_positions,
    num_rotatable_bonds,
    cutoff=8.0,
)
```

This is fixed-pose analysis, not docking or atom typing. Both type arrays
already contain Vina XS type names, and both position arrays contain Cartesian
coordinates in angstrom. Evaluate only receptor–ligand pairs with distance
strictly below `cutoff`; do not evaluate within-group pairs.

Supported XS types are:

```text
C_H C_P N_P N_D N_A N_DA O_P O_D O_A O_DA S_P P_P
F_H Cl_H Br_H I_H Si At Met_D
```

Use the AutoDock Vina 1.2.7 default `vina` scoring definition: gauss1, gauss2,
repulsion, hydrophobic, non-directional hydrogen bonding, and the standard
rotatable-bond normalization. Coordinate-force behavior at piecewise-linear
kinks must match the symmetric radial derivative of the locked donor.

## Return value

Return a JSON-serializable dictionary with exactly these required fields:

- `affinity`: normalized total in kcal/mol.
- `raw_interaction`: sum before rotatable-bond normalization.
- `torsional_penalty`: `affinity - raw_interaction`.
- `torsional_divisor`: the normalization divisor.
- `terms`: weighted raw sums named `gauss1`, `gauss2`, `repulsion`,
  `hydrophobic`, and `hydrogen`.
- `pairs`: included pairs in receptor-major, ligand-minor order. Each record has
  `receptor_index`, `ligand_index`, `receptor_type`, `ligand_type`, `distance`,
  the five weighted raw `terms`, and `raw_total`.
- `receptor_forces` and `ligand_forces`: one `[x, y, z]` vector per atom in
  kcal/mol/angstrom, after rotatable-bond normalization.

The raw interaction must equal both the term sum and the per-pair raw-total
sum. Forces on the two groups must sum to zero. A common rigid transformation
must preserve scores and rotate forces accordingly. Pairs at or beyond the
requested cutoff contribute exactly zero.

## Validation contract

Reject invalid values by raising an exception. Types and positions must be
lists of equal length, with at most 256 atoms per group. Every position must be
a finite numeric three-vector. `num_rotatable_bonds` must be a non-boolean
integer from 0 through 64. `cutoff` must be finite and in `(0, 8]`. Reject
coincident receptor/ligand atoms (distance at most `1e-6`). Empty groups are
valid and have zero interaction.

## Public examples

Five examples and locked expected results are in `/examples`. Run them with:

```bash
/opt/task-tools/run-public-examples
```

The separate offline verifier uses additional hidden typed poses and calls
locked native AutoDock Vina 1.2.7 potential classes as its reference. It also
checks invalid inputs, exact pair inclusion, score decomposition, forces,
source-tree integrity, prohibited dependencies, provenance, and runtime
isolation. Hidden-test reward is the fraction passed; a hard-gate failure earns
zero.
