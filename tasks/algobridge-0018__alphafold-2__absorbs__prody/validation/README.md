# Validation

Author-side validation exercises the task at four calibration points:

- **Oracle:** the clean-room GNM/ANM implementation under `solution/`;
- **NOP:** pristine locked AlphaFold without the requested module;
- **isotropic ANM near miss:** exact GNM behavior and all protocol/isolation
  gates, but an ANM built from isotropic Cartesian springs instead of the
  directional Hessian;
- **forbidden dependency:** an otherwise complete implementation that imports
  ProDy and must receive zero before candidate execution.

Public fixtures are generated only through the locked AlphaFold-to-ProDy
reference by `generate_public_examples.py` and are independently replayed in
the Agent image by `/opt/task-tools/run-public-examples`.

## Direct calibration results

- Oracle: 15/15, Reward 1.0;
- NOP: integration source gate, Reward 0.0;
- isotropic ANM near miss: 8/15, Reward 0.5333333333, with all source,
  isolation, invalid-input, protocol, and rigid-transform gates passing;
- forbidden ProDy import: dependency source gate, Reward 0.0;
- public examples: 5/5.

Machine-readable verifier reports and rewards are retained under `evidence/`.
Formal Harbor Oracle and NOP each complete one trial with zero exceptions or
retries, Rewards 1.0 and 0.0 respectively, and successful `/testbed` artifact
collection.  The final job/trial/lock/verifier snapshots are stored here after
the accepted task state is rerun.
