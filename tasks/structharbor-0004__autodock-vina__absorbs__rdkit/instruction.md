# Add native MMFF94 ligand strain energy to AutoDock Vina

Work in `/testbed`, a complete locked AutoDock Vina 1.2.7 source tree. A
complete RDKit 2026.03.5 source tree is available for documentation at
`/opt/donor-source`. Implement the bounded downstream capability inside Vina;
the final solution must not invoke, import, bundle, or depend on RDKit.

Add exactly one UTF-8 Python source file:

```text
build/python/vina/mmff94.py
```

Do not modify or remove any existing Vina file. The module must use only the
Python standard-library `math` module (plus an optional `__future__` import).

## Required API

```python
score_mmff94(packet)
```

The input is a preparameterized, fixed-geometry MMFF94 interaction packet. It
contains Cartesian coordinates in angstrom and the exact bonded/nonbonded terms
already selected and parameterized upstream. This task covers energy
evaluation, not atom typing, parameter assignment, conformer generation,
minimization, or docking.

Every packet has `schema` equal to
`structharbor-vina-rdkit-mmff94-v1`, a `positions` list, and these term lists:

- `bonds`: `atoms=[i,j]`, `kb`, `r0`.
- `angles`: `atoms=[i,j,k]`, `ka`, `theta0` in degrees, and Boolean `linear`.
- `stretch_bends`: `atoms=[i,j,k]`, `kba_ijk`, `kba_kji`, `r0_ij`,
  `r0_jk`, and `theta0` in degrees.
- `out_of_plane`: `atoms=[i,j,k,l]` and `koop`; `j` is central and the
  oriented `i-j-k` plane defines the signed angle to `l`.
- `torsions`: `atoms=[i,j,k,l]`, `v1`, `v2`, and `v3`.
- `nonbonded`: `atoms=[i,j]`, scaled `r_star`, scaled `epsilon`,
  `charge_term` (the partial-charge product divided by dielectric constant),
  `dielectric_model` (`1` for constant or `2` for distance-dependent), and
  Boolean `is_1_4`.

Parameters and output energies use RDKit's MMFF94 units: angstrom and kcal/mol.
Evaluate every supplied record exactly once and do not infer additional terms.

## Return value

Return a JSON-serializable dictionary with exactly these finite numeric fields:

```text
bond
angle
stretch_bend
out_of_plane
torsion
van_der_waals
electrostatic
total
```

Each component is its summed MMFF94 energy. `total` is the arithmetic sum of
the seven components. The result must be invariant to a common rigid
transformation and to reordering records within a term list.

## Validation contract

Reject invalid values by raising an exception. `packet` must be a dictionary
with the required schema. `positions` must contain 1 through 256 finite numeric
three-vectors. Atom indices must be non-Boolean integers, in range, and distinct
within each record. Reject malformed term lists, invalid Boolean/enumerated
fields, non-finite parameters, nonpositive equilibrium distances or VdW radii,
negative force constants/well depths where physically constrained, and
degenerate coordinate geometry needed by a supplied record.

To keep runtime bounded, accept at most 512 bonds, 4,096 angles, 4,096
stretch-bends, 4,096 out-of-plane terms, 8,192 torsions, and 32,768 nonbonded
pairs.

## Public examples

Five complete packets and locked expected results are in `/examples`. Run them
after creating the module:

```bash
/opt/task-tools/run-public-examples
```

The separate offline verifier uses additional hidden molecules. Its root-only
reference imports the locked official RDKit 2026.03.5 wheel, asks RDKit to
construct MMFF94 properties and force fields, and evaluates each native energy
component independently. It also checks invalid inputs, decomposition and sum
invariants, rigid-transform and record-order metamorphisms, source-tree
integrity, prohibited dependencies, provenance, and runtime isolation. Hidden
reward is the fraction passed; a hard-gate failure earns zero.
