# ALGOBRIDGE-0023 — LAMMPS absorbs MLIP

This Harbor task asks an agent to add a native, bounded single-element Moment
Tensor Potential energy/force/virial evaluator as LAMMPS
`pair_style mtp_bounded`. The separate verifier uses the locked official
MLIP-3 implementation as a root-only scientific oracle and runs offline.

See `instruction.md` for the participant contract and `source-lock.json` for
exact upstream and runtime provenance.

