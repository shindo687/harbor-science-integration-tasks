# Harbor acceptance: ALGOBRIDGE-0023

## Formal runs

- Harbor: `0.20.0`
- Functional task commit: `77a87af6dd6cb1ec29ff2ce54ca63a42eccdb488`
- Locked task digest shared by both jobs:
  `sha256:a53906abe804b686d1d0a7beefda6f7bf07ebd07e614c9a97b321d2baff9190d`
- Oracle job: `algobridge-0023-oracle-final-20260815`
- Oracle trial: `algobridge-0023__lammps__absorbs__8WePWJ2`
- Oracle reward: `1.0`; exceptions: none
- NOP job: `algobridge-0023-nop-final-20260815`
- NOP trial: `algobridge-0023__lammps__absorbs__7diP6vS`
- NOP reward: `0.0`; exceptions: none

Both formal jobs forced fresh Docker builds with CPU and memory enforcement
ignored only at the local Harbor adapter boundary. The verifier itself used the
task's locked no-network, separate-environment configuration.

## Oracle verification

The native LAMMPS pair style passed every gate:

- source integrity, include/process policy, and donor-copy scan: pass
- host/donor archives, runtime binary, libraries, and potential provenance: pass
- candidate UID 10001 isolation from all protected reference paths: pass
- pair-style registration and clean LAMMPS rebuild: pass
- disclosed scientific cases: `5/5`
- hidden scientific cases: `15/15`
- energy/force/virial components: `60/60`
- invalid cutoff, atom-type, malformed-potential, and missing-potential inputs: `4/4`
- translation and atom-permutation metamorphic checks: `2/2`

The root-only oracle ran the locked official MLIP-3 MTP implementation. Candidate
code executed only after the packet boundary and could not read the oracle,
donor source, pristine host, source archives, source locks, hidden cases, or
verifier implementation.

## Negative controls

The pristine LAMMPS host received Reward `0.0` because the required
`pair_mtp_bounded` source was absent. A realistic near miss implementing the
full bounded MTP energy/force calculation but omitting virial tallying received
Reward `0.7` (`42/60` scientific components). This demonstrates that full
reward requires all three migrated outputs, including the tensor virial.

## Evidence files

`validation/evidence/` contains the formal job locks, job and trial results,
artifact manifests, full Oracle/NOP verifier reports, and direct Oracle/NOP and
no-virial near-miss reports. Formal JSON files are copied byte-for-byte from the
corresponding Harbor job directories.
