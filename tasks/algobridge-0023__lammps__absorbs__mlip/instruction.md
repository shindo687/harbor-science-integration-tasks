# Add a native bounded MTP evaluator to LAMMPS

Work in `/testbed`, a complete locked LAMMPS `stable_22Jul2025_update5`
source tree. A locked official MLIP-3 source tree is available for algorithm
documentation at `/opt/donor-source/mlip-3`. Implement inference natively in
LAMMPS; the submitted code must not invoke, import, link, bundle, or dynamically
load MLIP.

Add exactly these two UTF-8 source files. Do not modify or remove existing
LAMMPS files:

```text
src/pair_mtp_bounded.h
src/pair_mtp_bounded.cpp
```

Register a LAMMPS pair style named `mtp_bounded` so this native input contract
works:

```text
units metal
atom_style atomic
boundary p p p
read_data atoms.data
pair_style mtp_bounded 5.0
pair_coeff * * /opt/candidate-assets/mtp9-bounded.mtp
run 0
```

## Bounded scientific contract

- Support exactly one atom type and one species; reject multi-type systems.
- `pair_style mtp_bounded` takes exactly one positive finite cutoff. It must
  equal the potential's `max_dist` (5.0 for the locked potential).
- `pair_coeff` takes exactly `* * potential.mtp` and reads MLIP's text MTP
  format. The bounded format is version 1.1.0, one species, `RBChebyshev`, two
  radial basis functions, two radial functions, and the locked MTP-9 topology:
  36 moment slots, 26 elementary tensor components, 39 contraction operations,
  and 9 scalar moment features. Its maximum contraction level is fixed at 12
  under the `2 + 2*mu + nu` convention; training is out of scope.
- Evaluate the total site-energy sum, analytic Cartesian forces, and the full
  symmetric virial. Use a full LAMMPS neighbor list and periodic LAMMPS
  displacements. Results must be available through ordinary LAMMPS thermo,
  force-dump, pressure, and stress mechanisms.
- The evaluated domain has 1–20 atoms, orthorhombic periodic boxes with each
  length at least 11 angstrom, and no pair distance below the potential's
  1.278499028431387-angstrom inner distance. Neighbors at or beyond the cutoff
  make no contribution.
- Reject malformed or unsupported potential files, missing files, a cutoff
  mismatch, and unsupported atom-type counts. Do not hard-code disclosed
  configurations or their outputs.

You may use LAMMPS core APIs and the C++ standard library. File I/O is allowed
only to read the coefficient file selected by `pair_coeff`. Process launch,
network access, dynamic loading, and private verifier paths are forbidden.

## Validation

After adding the two files, run the five disclosed official-MLIP comparisons:

```bash
/opt/task-tools/check-mtp-public
```

The separate no-network verifier rebuilds locked LAMMPS and runs the candidate
as UID 10001. A root-only executable built from the exact locked MLIP-3 commit
is the oracle. It checks five public and fifteen hidden configurations, scoring
energy, forces, and six-component virial separately (60 scientific components),
plus four invalid-input rejections, translation and atom-permutation identities,
source integrity, provenance, and candidate/reference isolation. Hard-gate
failures earn zero.

