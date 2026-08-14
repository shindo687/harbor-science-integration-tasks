# Author validation assets

- `evidence/oracle-report.json`: direct clean-room Oracle, `15/15`, Reward 1.
- `evidence/nop-report.json`: pristine SciPy baseline, `0/15`.
- `evidence/near-miss-report.json`: OLS-only superficial implementation,
  `0/15`.
- `evidence/public-examples-report.json`: frozen public examples, `5/5`.
- `evidence/harbor-oracle-job-result.json` and
  `evidence/harbor-oracle-verifier-report.json`: Harbor Oracle, 1 trial,
  0 exceptions, `15/15`, Reward 1.
- `evidence/harbor-nop-job-result.json` and
  `evidence/harbor-nop-verifier-report.json`: Harbor NOP, 1 trial,
  0 exceptions, `0/15`, Reward 0.
- `near_miss.py` and `install_near_miss.py`: score-separation implementation.
- `generate_public_expected.py`: reproducible public reference freezer.
- `BUILD_PROVENANCE.md`: exact source and wheel build record.

Harbor does not expose `solution/`, `validation/`, or verifier-private files to
the Agent.

