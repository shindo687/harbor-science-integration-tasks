# Validation

Author-side validation exercises four calibration points:

- **Oracle:** the clean-room, NumPy-only GROMACS gmxapi ANM implementation in
  `solution/`;
- **NOP:** pristine locked GROMACS without the requested analysis module;
- **unnormalized-spring near miss:** the correct ANM protocol and directional
  outer product, but without division by squared inter-node distance;
- **forbidden dependency:** an otherwise complete module imports ProDy and must
  receive zero before candidate execution.

The five public fixtures are produced only by the locked ProDy
`ANM.buildHessian` / `ANM.calcModes` reference via
`generate_public_examples.py`. Regeneration is byte-for-byte deterministic;
all five replay successfully in the Agent image, where ProDy, SciPy, and
Biopython are absent.

## Accepted calibration

- Oracle: 15/15, Reward 1.0;
- NOP: missing integration source gate, Reward 0.0;
- unnormalized-spring near miss: 0/15, Reward 0.0, with source, isolation,
  invalid-input, protocol, rigid-transform, gamma-scaling, and atom-reordering
  gates passing;
- forbidden ProDy import: dependency source gate, Reward 0.0;
- public examples: 5/5.

Formal Harbor 0.20 Oracle and NOP each completed one trial with zero exceptions
or retries, Rewards 1.0 and 0.0 respectively, and successful `/testbed`
artifact collection. Both task locks record publishable task digest
`sha256:76fdf3305101bd3a0fbd75570824c3362150978c004b59e1a028c95e1718dfff`.
Machine-readable direct and Harbor evidence is retained under `evidence/`.
