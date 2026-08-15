# Harbor acceptance: ALGOBRIDGE-0008

## Formal runs

- Harbor: `0.20.0`
- Functional task commit: `503252ee49f5955a6a7078baa66af46b097455a5`
- Locked task digest shared by both jobs:
  `sha256:ccf503bfd9b23fcf809ae3e30a7658e2db5529dfdac82fa231366e8a1b6741b1`
- Oracle job: `algobridge-0008-oracle-final-20260816`
- Oracle trial: `algobridge-0008__hhblits__absorb__5JDEbzB`
- Oracle reward: `1.0`; exceptions: none
- NOP job: `algobridge-0008-nop-final-20260816`
- NOP trial: `algobridge-0008__hhblits__absorb__GXFug2J`
- NOP reward: `0.0`; exceptions: none

Both jobs forced fresh Docker builds with CPU and memory enforcement ignored
only at the local Harbor adapter boundary. The verifier itself used the task's
locked no-network, separate-environment configuration.

## Oracle verification

The native HH-suite C++ command passed every gate:

- source integrity, bounded CMake registration, and forbidden-runtime policy: pass
- 23,492 locked donor token windows checked with no 64-token copy: pass
- host/donor archives, reference binary, build patch, and source locks: pass
- candidate UID 10001 isolation from every protected verifier path: pass
- clean GNU C++ build and standalone linkage check: pass
- disclosed scientific cases: `5/5`
- hidden scientific cases: `15/15`
- raw/APC correlation, top-L/2 overlap, and objective components: `80/80`
- malformed parameter/A3M rejection modes: `8/8`
- alignment-row permutation invariance: pass

The root-only oracle ran locked official CCMpred in deterministic,
double-precision CPU mode. Candidate code executed only after the packet
boundary and could not read the oracle, donor source, pristine host, source
archives, source locks, hidden cases, or verifier implementation.

## Negative controls

The pristine HH-suite host received Reward `0.0` because `src/hhcontacts.cpp`
was absent. A realistic near miss that used `L-2` rather than CCMpred's `L-1`
pairwise regularization scaling received Reward `0.65` (`52/80` scientific
components). It retained a working native optimizer and often preserved the
top contacts, while failing exact objectives and multiple score-correlation
checks.

## Evidence files

`validation/evidence/` contains the formal job locks, job and trial results,
artifact manifests, full Oracle/NOP verifier reports, and direct Oracle/NOP and
regularization near-miss reports. Formal JSON files are copied byte-for-byte
from the corresponding Harbor job directories.
