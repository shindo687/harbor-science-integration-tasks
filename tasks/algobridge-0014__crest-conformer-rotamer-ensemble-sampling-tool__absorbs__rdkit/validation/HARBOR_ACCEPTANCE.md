# Formal Harbor acceptance

Accepted with Harbor 0.20.0's local Docker provider on 2026-08-15. Both formal
trials used `environment_mode = "separate"` and
`network_mode = "no-network"`; each completed once with no retry or exception.

## Oracle

- Job: `algobridge-0014-oracle-final-20260815`
- Job result ID: `0d398b39-7d79-46cf-a225-2b1e9ddd6eb6`
- Trial: `algobridge-0014__crest-conformer__8xKdKZR`
- Trial result ID: `a541b253-0cb1-4a8a-bdce-7a6cba3c0e6a`
- Trial task checksum: `f7542074590e826cd7cadea9721fabf3f1dd859369f1bc337624e367b123d34c`
- Task lock digest: `sha256:c8be3240fdf1e38a5930d1a03dab6209364c0b2d1a1531b82c932a190b854280`
- Result: one completed trial, zero errors, zero retries, Reward `1.0`
- Verifier: source/provenance/isolation gates passed; public `5/5`, hidden
  `15/15`, invalid contract `12/12`, metamorphic `2/2`

## NOP

- Job: `algobridge-0014-nop-final-20260815`
- Job result ID: `c1b0c1a1-682e-4a13-8e60-3209c12ffe3b`
- Trial: `algobridge-0014__crest-conformer__7fdnkJF`
- Trial result ID: `d5fb3386-b56a-40f4-b2f5-67858a4a88fa`
- Trial task checksum: `f7542074590e826cd7cadea9721fabf3f1dd859369f1bc337624e367b123d34c`
- Task lock digest: `sha256:c8be3240fdf1e38a5930d1a03dab6209364c0b2d1a1531b82c932a190b854280`
- Result: one completed trial, zero errors, zero retries, Reward `0.0`
- Verifier: source gate rejected the absent integration module as expected

## Interpretation

The clean-room Oracle matches official RDKit 2026.03.5 ETKDGv3 topology-bound
smoothing exactly on all five disclosed and fifteen hidden molecules. Across
the accepted ensemble, the worst bound violation is `0.2840618755 angstrom`
against a `0.35 angstrom` limit, and the worst native distance-matrix coverage
is `0.7053786865 angstrom` against a `0.80 angstrom` limit. Fixed-seed
determinism and bound-record reordering both pass. The candidate UID cannot
read any of the seven protected reference, source, wheel, test, pristine-host,
runner, or archive paths.

The NOP proves pristine CREST lacks the requested module. A scientific near
miss that ignores chirality passes only `4/5` public and `11/15` hidden cases
(Reward `0.7333333333`), failing five stereochemical molecules while retaining
valid distance geometry. This demonstrates that the verifier distinguishes a
plausible incomplete implementation while preserving partial reward.

The functional task files exercised by both formal trials were committed at
`9c2c67fcf4ab7f1610f325c422619fd9d2f05351`; accepted-state metadata and the
copied machine-readable evidence were added afterward.
