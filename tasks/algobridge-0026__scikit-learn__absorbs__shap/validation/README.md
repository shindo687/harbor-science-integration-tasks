# Author validation assets

- `evidence/direct-oracle-report.json`: direct clean-room Oracle, `15/15`,
  Reward 1.
- `evidence/direct-nop-report.json`: pristine scikit-learn baseline, `0/15`.
- `evidence/near-miss-report.json`: single decision-path/Saabas-style
  approximation, `2/15`, Reward `0.133333333333`.
- `evidence/public-examples-report.json`: frozen public examples, `5/5`.
- `evidence/harbor-oracle-job-result.json`, verifier report, and artifact
  manifest: Harbor Oracle, one trial, zero errors, `15/15`, Reward 1.
- `evidence/harbor-nop-job-result.json`, verifier report, and artifact manifest:
  Harbor NOP, one trial, zero errors, `0/15`, Reward 0.
- `near_miss.py` and `install_near_miss.py`: score-separation implementation.

The final verifier reports record the locked source/wheel identity, fresh
differential comparisons, hard-gate results, candidate overlay, and upstream
regression output. Harbor does not expose `solution/`, `validation/`, or
verifier-private files to the Agent.
