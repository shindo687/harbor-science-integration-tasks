# Validation matrix

Final results from 2026-08-14 are:

- `evidence/oracle-report.json`: clean-room Oracle, `15/15`, Reward 1;
- `evidence/nop-report.json`: pristine Scanpy, Reward 0;
- `evidence/near-miss-report.json`: global-kNN superficial solution, `0/15`, Reward 0;
- `evidence/public-examples-report.json`: frozen public examples, `5/5`;
- `evidence/harbor-oracle-job-result.json` and
  `evidence/harbor-oracle-verifier-report.json`: Harbor Oracle, 1 trial,
  0 exceptions, `15/15`, Reward 1;
- `evidence/harbor-nop-job-result.json` and
  `evidence/harbor-nop-verifier-report.json`: Harbor NOP, 1 trial,
  0 exceptions, Reward 0.

`install_near_miss.py` installs the deliberately incomplete global-kNN implementation. Harbor does
not expose `solution/`, `validation/`, or verifier-private files to the Agent.
