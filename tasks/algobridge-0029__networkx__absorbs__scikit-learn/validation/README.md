# Author validation assets

- `near_miss.py` is an intentionally wrong implementation that returns
  deterministic contiguous labels and zero spectral observables.  It checks
  that superficial API compliance cannot receive full credit.
- `evidence/oracle-report.json` is the final clean-room direct-container
  Oracle report (`15/15`, Reward `1.0`).
- `evidence/nop-report.json` is the pristine NetworkX baseline (`0/15`).
- `evidence/near-miss-report.json` is the superficial implementation result
  (`2/15`).
- `evidence/harbor-oracle-job-result.json` and
  `evidence/harbor-oracle-verifier-report.json` record the passing Harbor
  Oracle trial (`15/15`, Reward `1.0`, 0 exceptions).
- `evidence/harbor-nop-job-result.json` and
  `evidence/harbor-nop-verifier-report.json` record the passing Harbor NOP
  baseline (`0/15`, Reward `0.0`, 0 exceptions).

These files are authoring evidence.  Harbor does not copy `solution/` or
`validation/` into the Agent environment.
