# Validation protocol

The task is accepted only after all of the following use the same committed
task content:

1. the clean-room Oracle passes all public examples and all 15 private points;
2. pristine OpenMM (NOP) scores zero through the missing-integration hard gate;
3. a scientifically plausible estimator with correct free energies but the
   approximate `W.T @ W` covariance passes isolation/source/API gates and is
   rejected by the differential scientific points;
4. formal Harbor Oracle and NOP trials finish with no exception or retry.

The final evidence snapshots are stored under `validation/evidence/` after the
formal Harbor runs. They contain reports and task/result metadata, never model
credentials or private external services.

## Final accepted evidence

- `direct-oracle-report.json`: clean-room Oracle `15/15`, Reward `1.0`;
- `direct-nop-report.json`: pristine source rejected by the integration gate;
- `direct-near-miss-report.json`: approximate covariance `3/15`, Reward `0.2`,
  with all hard gates passing;
- `harbor-oracle-*-result.json` and `harbor-oracle-verifier-report.json`:
  formal Oracle trial, Reward `1.0`, zero exception/retry;
- `harbor-nop-*-result.json` and `harbor-nop-verifier-report.json`: formal NOP
  trial, Reward `0.0`, zero exception/retry;
- `harbor-*-artifact-manifest.json`: both `/testbed` collections are `ok`.
