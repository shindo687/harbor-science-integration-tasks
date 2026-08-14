# Validation matrix

The release gate is intentionally broader than a successful Oracle run. Final
results from 2026-08-14 are:

- `evidence/oracle-report.json`: clean-room Oracle, `15/15`, Reward 1;
- `evidence/nop-report.json`: pristine Scanpy, `0/15`;
- `evidence/near-miss-report.json`: uniform-probability superficial solution,
  `0/15`, despite passing the API/regression and invariant gates;
- `evidence/public-examples-report.json`: frozen public examples, `5/5`;
- `evidence/harbor-oracle-job-result.json` and
  `evidence/harbor-oracle-verifier-report.json`: Harbor Oracle, 1 trial,
  0 exceptions, `15/15`, Reward 1;
- `evidence/harbor-nop-job-result.json` and
  `evidence/harbor-nop-verifier-report.json`: Harbor NOP, 1 trial,
  0 exceptions, `0/15`, Reward 0.

`install_near_miss.py` installs the deliberately incomplete score-separation
implementation. Harbor does not expose `solution/`, `validation/`, or any
verifier-private file to the Agent.
