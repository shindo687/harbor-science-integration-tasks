# Validation

Author-side validation checks the task at three calibration points:

- Oracle: the clean-room fixed-point reversible MLE in `solution/`
- NOP: pristine locked OpenMM without the requested API
- Near miss: exact counting and all protocol/isolation gates, but reversible
  estimation incorrectly row-normalizes `C + C.T`
- Forbidden dependency: an otherwise complete module that imports PyEMMA and
  must receive zero before candidate execution

The verifier report and Harbor result snapshots are stored under `evidence/`.

## Accepted calibration

- direct Oracle: 15/15, Reward 1.0;
- direct NOP: integration hard gate, Reward 0.0;
- direct symmetrization near miss: 10/15, Reward 0.6666666667, with all
  source/isolation/protocol gates passing;
- forbidden PyEMMA import: source hard gate, Reward 0.0;
- public examples: 5/5;
- formal Harbor Oracle and NOP: one trial each, zero exceptions/retries,
  Rewards 1.0 and 0.0, both `/testbed` artifact collections `ok`.
