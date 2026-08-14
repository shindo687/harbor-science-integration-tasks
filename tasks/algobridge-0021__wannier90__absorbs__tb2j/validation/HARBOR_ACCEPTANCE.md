# Formal Harbor acceptance

Accepted with Harbor 0.20's local Docker provider on 2026-08-15. Both trials
used the task's `environment_mode = "separate"` and `network_mode =
"no-network"`; each completed once with no retry and no exception.

## Oracle

- Job: `algobridge-0021-wannier90-tb2j-oracle-r1-20260815`
- Job result ID: `fe1f038e-22cf-4aee-9e31-2475ab890d89`
- Trial: `algobridge-0021__wannier90__abso__wJJEh8P`
- Trial result ID: `a5305172-4b70-4230-b798-3686e3d8efe0`
- Task checksum: `43237884199379add0271f779559f50ed959aea49152cd6ab853ee1810eecd90`
- Task lock digest: `sha256:2585ef994b15852198cdb060064698124ae9baae7871027f496022a9a2c9ad16`
- Result: one completed trial, zero errors, Reward `1.0`
- Verifier: public `5/5`, hidden `15/15`, invalid `10/10`, metamorphic `2/2`

## NOP

- Job: `algobridge-0021-wannier90-tb2j-nop-r1-20260815`
- Job result ID: `97848478-7fa1-49d5-b29e-368054bb828c`
- Trial: `algobridge-0021__wannier90__abso__JYsbJyp`
- Trial result ID: `4a160734-629b-48c3-ae03-e016dad1e387`
- Task checksum: `43237884199379add0271f779559f50ed959aea49152cd6ab853ee1810eecd90`
- Task lock digest: `sha256:2585ef994b15852198cdb060064698124ae9baae7871027f496022a9a2c9ad16`
- Result: one completed trial, zero errors, Reward `0.0`
- Verifier: public `0/5`, hidden `0/15`, invalid `9/10`, metamorphic `0/2`
- Failure reason: pristine Wannier90 does not contain
  `src/liechtenstein_exchange.F90`

## Interpretation

The Oracle result proves that the clean-room Wannier90-side implementation
reproduces the locked real TB2J `0.9.19` reference across the complete matrix
under candidate isolation. The NOP result proves that unchanged upstream
Wannier90 cannot pass. The additional always-ferromagnetic-sign near miss still
performs the complex-contour Green-function calculation but mishandles
antiferromagnetic pairs; it scores `11/15` hidden cases, so the verifier detects
a plausible but scientifically incomplete solution.

The functional task files exercised by these trials were committed at
`87b8482b7e9c04a18e85cba947051787b9567c61`; this acceptance document and the
copied Harbor result artifacts were added afterward.
