# ALGOBRIDGE-0011: GROMACS absorbs DSSP

Harbor single-step algorithm-migration task. The Agent adds a native
`gmx dssp-internal` analysis command to locked GROMACS 2024.6. The separate,
offline verifier runs locked real `mkdssp 4.4.11` on the same multi-frame
protein backbones, removes the reference implementation, then compiles and
runs the candidate as an unprivileged user.

Scope includes DSSP hydrogen-bond energies and H/G/I/E/B/T/S/C assignment,
multiple frames, missing backbone atoms, chain breaks, and orthorhombic-PBC
unwrapping. The rare DSSP `P` extension is normalized to C.

Accepted validation:

- Oracle: public 5/5, hidden 15/15, invalid inputs 10/10, Reward 1.0.
- Pristine/NOP baseline: rejected by the source-policy hard gate, Reward 0.
- Original GROMACS version/help/`gmx analyze` regression: pass.
- Agent-container public command: 5/5 with networking disabled.
- Formal Harbor 0.20.0 jobs: Oracle 1.0, NOP 0, one trial each, zero
  exceptions.

Oracle job `bca4a517-e607-4913-b190-7e74cfe87634` used trial
`6bc3e6ab-9796-403b-aec2-a5a3c5aa6055`; NOP job
`dd25a941-f132-4138-a59e-eddfa02a560c` used trial
`75007034-6c32-414a-acbf-2896fe51a742`. Exact source, runtime, fixture, and
image identities are in `source-lock.json`; machine-readable evidence and
checksums are under `validation/evidence/`.
