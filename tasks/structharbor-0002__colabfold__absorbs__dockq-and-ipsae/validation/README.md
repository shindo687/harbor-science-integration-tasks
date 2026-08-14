# Author validation assets

- `evidence/direct-oracle-report.json`: final direct Oracle, `15/15`, Reward 1.
- `evidence/direct-nop-report.json`: pristine ColabFold, `0/15`.
- `evidence/dockq-only-report.json`: only DockQ plus integration shell,
  `7/15`.
- `evidence/ipsae-only-report.json`: only ipSAE plus integration shell,
  `7/15`.
- `evidence/public-examples-report.json`: public examples, `5/5`.
- `evidence/harbor-oracle-*`: final Harbor Oracle job result, verifier report,
  and artifact manifest; one trial, zero errors, Reward 1.
- `evidence/harbor-nop-*`: final Harbor NOP job result, verifier report, and
  artifact manifest; one trial, zero errors, Reward 0.
- `install_near_miss.py`: deterministic one-donor baseline installer.

`solution/`, `validation/`, and verifier reference material are not visible in
the Agent container.
