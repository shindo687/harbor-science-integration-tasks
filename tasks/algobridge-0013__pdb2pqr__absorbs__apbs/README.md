# ALGOBRIDGE-0013: PDB2PQR absorbs APBS

Accepted Harbor single-step algorithm-migration Task. The bounded target
is the APBS 3.4.1 uniform-grid linearized Poisson-Boltzmann finite-volume solve
inside the locked PDB2PQR 3.7.1 source tree.

## Acceptance state

Official host and donor commits, complete ordinary tracked-source archives, the
official APBS Linux release, an immutable Python base image, and an offline
NumPy runtime are provenance-locked. Harbor 0.20.0 accepted the clean-room
Oracle at Reward `1.0` and rejected the pristine-host NOP at Reward `0.0`.
The Oracle passes public `5/5`, hidden `15/15`, invalid-contract `12/12`, and
metamorphic `2/2` checks. A deliberate solver omitting ionic screening scores
only `0.05`.

Exact commits, trees, archive policy, file counts, hashes, and runtime identities
are recorded in [`source-lock.json`](source-lock.json). Formal machine-readable
evidence and interpretation are recorded in
[`validation/HARBOR_ACCEPTANCE.md`](validation/HARBOR_ACCEPTANCE.md).
