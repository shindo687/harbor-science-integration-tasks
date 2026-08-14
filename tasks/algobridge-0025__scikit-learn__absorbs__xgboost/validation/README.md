# Validation

Author-side validation exercises four calibration points:

- **Oracle:** the clean-room NumPy exact second-order implementation in
  `solution/`;
- **NOP:** pristine locked scikit-learn without the requested estimator;
- **doubled-Hessian near miss:** a plausible loss-convention error that keeps
  the full protocol, missing-direction logic, L1 behavior, and determinism but
  doubles every gradient Hessian;
- **forbidden dependency:** the otherwise complete Oracle imports XGBoost and
  must receive zero before candidate execution.

The five public fixtures are produced only by locked XGBoost
`a3e3df59b83e1f230bb238c99dbaf63d8382ed24` with exact CPU training via
`generate_public_examples.py`. Regeneration is byte-for-byte deterministic;
all five replay successfully in the Agent image, where XGBoost, LightGBM, and
CatBoost are absent.

## Accepted calibration

- Oracle: 15/15, Reward 1.0;
- NOP: missing integration source gate, Reward 0.0;
- doubled-Hessian near miss: 0/15, Reward 0.0, with source, isolation,
  invalid-input, host-regression, zero-rate, missing-direction, L1, and
  permutation hard gates passing;
- forbidden XGBoost import: dependency source gate, Reward 0.0;
- public examples: 5/5.

Formal Harbor 0.20 Oracle and NOP each completed one trial with zero exceptions
or retries, Rewards 1.0 and 0.0 respectively, and successful `/testbed`
artifact collection. Both task locks record publishable task digest
`sha256:86aad060d67b98ba1c0d8cdc4d6d20cce623b62fb3d3f1b0f9ff67e6d5b666b5`.
Machine-readable direct and Harbor evidence is retained under `evidence/`.
