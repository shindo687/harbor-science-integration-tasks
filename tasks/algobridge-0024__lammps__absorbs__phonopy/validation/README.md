# Validation and accepted results

1. Lock and hash the LAMMPS host and phonopy donor snapshots.
2. Generate public and hidden force records by actually running pristine
   LAMMPS on finite displacements.
3. Run locked phonopy for FC2, q-point dynamical matrices, and modes.
4. Remove the reference executables/source and run candidate LAMMPS as an
   unprivileged user.
5. Enforce source-preservation, forbidden-dependency, invalid-input, host
   regression, numerical differential, and scientific-invariant gates.
6. Validate Oracle, NOP, and at least one algorithmic near miss before Harbor.

Accepted on 2026-08-14:

| Scenario | Passed | Reward |
|---|---:|---:|
| Direct clean-room Oracle | 15/15 | 1.0 |
| Direct pristine host (NOP) | 0/15 | 0.0 |
| Direct no-projection near miss | 0/15 final | 0.0 |
| Direct forbidden donor dependency | dependency gate | 0.0 |
| Formal Harbor Oracle | 15/15 | 1.0 |
| Formal Harbor NOP | source gate | 0.0 |

The no-projection implementation compiled and passed the host/dependency gates,
but failed the cross-input scientific invariants. The formal Oracle and NOP
each completed one trial with zero platform exceptions.

`evidence/` contains the immutable Harbor job/trial results and locks, verifier
reports and rewards, artifact manifests, direct negative-control reports, and a
`SHA256SUMS` manifest.
