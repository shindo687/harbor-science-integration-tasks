# Author validation assets

- `evidence/oracle-report.json`: clean-room Oracle, `15/15`, Reward `1.0`.
- `evidence/nop-report.json`: pristine scikit-learn baseline, `0/15`.
- `evidence/near-miss-report.json`: API-only implementation that performs no
  resampling, `0/15` while still passing isolation and host regression gates.
- `evidence/public-examples-report.json`: five published examples, `5/5`.
- `evidence/harbor-oracle-job-result.json` and
  `evidence/harbor-oracle-verifier-report.json`: passing Harbor Oracle,
  `15/15`, Reward `1.0`, 0 exceptions.
- `evidence/harbor-nop-job-result.json` and
  `evidence/harbor-nop-verifier-report.json`: passing Harbor NOP, `0/15`,
  Reward `0.0`, 0 exceptions.
- `near_miss.py` and `install_near_miss.py`: the representative superficial
  implementation used to check score separation.

These are authoring assets. Harbor does not expose `solution/`, `validation/`
or verifier-private files to the Agent.
