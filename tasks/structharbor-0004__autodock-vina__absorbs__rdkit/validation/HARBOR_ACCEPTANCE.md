# Formal Harbor acceptance

Accepted with Harbor 0.20.0's local Docker provider on 2026-08-15. Both formal
trials used `environment_mode = "separate"` and
`network_mode = "no-network"`; each completed once with no retry or exception.

## Oracle

- Job: `structharbor-0004-oracle-final-20260815`
- Job result ID: `1a231c11-081c-4a31-b9bf-79459029045d`
- Trial: `structharbor-0004__autodock-vina__NzarusG`
- Trial result ID: `7a6897bb-a288-4de5-9699-16890d9411ee`
- Trial task checksum: `ed66ea617bbe567c72393dc70f5a9857543edf1555c6d2d076655d69591da3bb`
- Task lock digest: `sha256:6dcf8f01192b34b545e18ee585585ad295f86702ff0acfbf57bde36a0c21703b`
- Result: one completed trial, zero errors, zero retries, Reward `1.0`
- Verifier: source/provenance/isolation gates passed; public `5/5`, hidden
  `15/15`, invalid `12/12`, metamorphic `2/2`

## NOP

- Job: `structharbor-0004-nop-final-20260815`
- Job result ID: `8277a48f-e7ce-4c0c-8b90-f0f5280c48c8`
- Trial: `structharbor-0004__autodock-vina__gj6NY7B`
- Trial result ID: `a597acc7-b94b-49b7-aead-af6431babd42`
- Trial task checksum: `ed66ea617bbe567c72393dc70f5a9857543edf1555c6d2d076655d69591da3bb`
- Task lock digest: `sha256:6dcf8f01192b34b545e18ee585585ad295f86702ff0acfbf57bde36a0c21703b`
- Result: one completed trial, zero errors, zero retries, Reward `0.0`
- Verifier: source gate rejected the absent integration module as expected

## Interpretation

The clean-room Oracle matches official RDKit 2026.03.5 MMFF94 force fields on
all five disclosed and fifteen hidden molecules. All seven energy components
and their total match with a maximum differential absolute error of
`8.53e-14 kcal/mol`. Both rigid-transform and record-order metamorphisms pass.
The candidate UID cannot read any of the seven protected reference, source,
wheel, test, pristine-host, runner, or archive paths.

The NOP proves pristine AutoDock Vina lacks the requested module. A scientific
near miss that omits out-of-plane energy passes only `5/15` hidden cases
(Reward `0.3333333333`), demonstrating that the verifier distinguishes a
plausible incomplete implementation while preserving partial reward.

The functional task files exercised by both formal trials were committed at
`dbfc4b7658c5e2bd139c12c0471917896cf251c3`; accepted-state metadata and the
copied machine-readable evidence were added afterward.
