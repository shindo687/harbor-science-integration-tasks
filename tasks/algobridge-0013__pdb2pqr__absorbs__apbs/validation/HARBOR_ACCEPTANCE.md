# Harbor acceptance: ALGOBRIDGE-0013

## Formal runs

- Harbor: `0.20.0`
- Functional task commit: `1a3593c410a2005703dc51ec34e20d68b92eab78`
- Locked task digest shared by both jobs:
  `sha256:69b38168356ef1aeba3d802f57f73f1c9a37eef02b021c1a30c758245310a469`
- Oracle job: `algobridge-0013-oracle-final-20260815`
- Oracle trial: `algobridge-0013__pdb2pqr__absorb__NvEAghZ`
- Oracle reward: `1.0`; exceptions: none
- NOP job: `algobridge-0013-nop-final-20260815`
- NOP trial: `algobridge-0013__pdb2pqr__absorb__ARDYQpc`
- NOP reward: `0.0`; exceptions: none

Both formal jobs forced fresh Docker builds with CPU and memory enforcement
ignored only at the local Harbor adapter boundary. The verifier itself used the
task's locked no-network, separate-environment configuration.

## Oracle verification

The clean-room solution passed every gate:

- source policy and donor-copy scan: pass
- provenance hashes and official APBS 3.4.1 smoke check: pass
- candidate UID 10001 isolation from every reference path: pass
- disclosed scientific cases: `5/5`
- hidden scientific cases: `15/15`
- malformed-packet contract: `12/12`
- operator/source scaling and sign-inversion metamorphic checks: `2/2`

The reference was the official APBS 3.4.1 Linux executable. It generated the
dielectric, accessibility, charge, Dirichlet boundary, native potential, and
native energy for each molecular system inside a root-only verifier path. The
candidate was evaluated independently from the resulting discretized packet.

## Negative controls

The pristine PDB2PQR host received Reward `0.0` because the exact required
`pdb2pqr/lpbe_grid.py` addition was absent. A plausible scientific near miss
that retained the full PCG implementation but omitted the ionic-screening term
received Reward `0.05`: it passed only the single zero-salt hidden case and
failed the other nineteen scientific cases. This demonstrates that the
scientific checks discriminate the target LPBE operator rather than generic
Poisson solves.

## Evidence files

`validation/evidence/` contains the formal job locks, job and trial results,
artifact manifests, full verifier reports for Oracle and NOP, and the
omit-salt near-miss report. The JSON files are copied byte-for-byte from the
corresponding Harbor job directories or the isolated development near-miss run.
