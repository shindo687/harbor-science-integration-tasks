# Validation

Author-side validation exercises four calibration points:

- **Oracle:** the clean-room constrained FC2/FC3 implementation in `solution/`;
- **NOP:** pristine locked phonopy without the requested module;
- **no-space-group near miss:** correct P1 fitting and protocol behavior, but
  crystallographic augmentation is omitted;
- **forbidden dependency:** an otherwise complete module imports phono3py and
  must receive zero before candidate execution.

The five public fixtures are produced only by the locked
`Phono3py.produce_fc3(fc_calculator="symfc", is_compact_fc=False)` reference via
`generate_public_examples.py`. Regeneration is byte-for-byte deterministic;
all five replay successfully in the Agent image, where phono3py and symfc are
absent.

## Accepted calibration

- Oracle: 15/15, Reward 1.0;
- NOP: missing integration source gate, Reward 0.0;
- no-space-group near miss: 10/15, Reward 0.6666666667, with source,
  isolation, invalid-input, protocol, rigid-rotation, and atom-reordering
  gates passing;
- forbidden phono3py import: dependency source gate, Reward 0.0;
- public examples: 5/5.

Formal Harbor 0.20 Oracle and NOP each completed one trial with zero exceptions
or retries, Rewards 1.0 and 0.0 respectively, and successful `/testbed`
artifact collection. Machine-readable direct and Harbor evidence is retained
under `evidence/`.
