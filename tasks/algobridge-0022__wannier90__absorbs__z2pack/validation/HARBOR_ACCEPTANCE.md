# Formal Harbor acceptance

Accepted with Harbor 0.20's local Docker provider on 2026-08-15. Both trials
used the task's `environment_mode = "separate"` and `network_mode =
"no-network"`; each completed once with no retry and no exception.

## Oracle

- Job: `algobridge-0022-wannier90-z2pack-oracle-r1-20260815`
- Job result ID: `2a8d76a9-b82f-4620-b7e5-3afbf5cf1a78`
- Trial: `algobridge-0022__wannier90__abso__Z4DXdvD`
- Trial result ID: `3746c830-a375-42b9-8b63-6445d97f0579`
- Task checksum: `cf16e42f86cdf1939e8be630c8c10ed8b62bb54ece8656aec0f15143e4970d0d`
- Task lock digest: `sha256:454561e6f0ea45acf3665b2b809629cb738a6f0d446f9864151a3a1ba2f433a9`
- Result: one completed trial, zero errors, Reward `1.0`
- Verifier: public `5/5`, hidden `15/15`, invalid/closure `10/10`, metamorphic `2/2`

## NOP

- Job: `algobridge-0022-wannier90-z2pack-nop-r1-20260815`
- Job result ID: `db0fdcd1-ccf6-49d8-a148-fee140f4317e`
- Trial: `algobridge-0022__wannier90__abso__4P7SXQL`
- Trial result ID: `51071af6-616e-4a8d-afd5-a4f06ebc6059`
- Task checksum: `cf16e42f86cdf1939e8be630c8c10ed8b62bb54ece8656aec0f15143e4970d0d`
- Task lock digest: `sha256:454561e6f0ea45acf3665b2b809629cb738a6f0d446f9864151a3a1ba2f433a9`
- Result: one completed trial, zero errors, Reward `0.0`
- Verifier: public `0/5`, hidden `0/15`, invalid/closure `9/10`, metamorphic `0/2`
- Failure reason: pristine Wannier90 does not contain `src/z2_wilson_loop.F90`

## Interpretation

The Oracle result proves that the clean-room Wannier90-side implementation
reproduces the locked real Z2Pack `v2.2.0` reference across the complete matrix
under candidate isolation. The NOP result proves that unchanged upstream
Wannier90 cannot pass. The additional always-trivial near miss still computes
WCC data but forces `Z2 = 0`; it scores `7/15` hidden cases, so the verifier
detects a plausible but scientifically incomplete solution.

The functional task files exercised by these trials were committed at
`b94f65e294e2981d47c497728643902e784935ed`; this acceptance document and the
copied Harbor result artifacts were added afterward.
