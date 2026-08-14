# Direct isolated verifier validation

The development verifier images were built from the task Dockerfiles with
rootless Podman and executed against independently materialized edgeR trees.

## Oracle

- Reward: `1`
- Public cases: `5/5`
- Hidden cases: `15/15`
- Invalid inputs rejected: `10/10`
- Reference deterministic replays: `2/2` identical
- Candidate identity: UID `10001`
- Candidate access to `/tests`: denied
- Candidate-writable paths under `/testbed`: none
- limma/statmod source and packages during candidate phase: absent
- Source policy: only `R/voomFit.R` added and one NAMESPACE export changed
- Donor fragment scan: pass at 64- and 96-token windows
- Maximum t-statistic discrepancy across the checked cases: floating-point
  roundoff only (approximately `3.2e-15`)

## NOP

- Reward: `0`
- Gate: rejected because `R/voomFit.R` was not added

This is development evidence, not formal Harbor acceptance. Formal acceptance
requires fresh `harbor run` Oracle and NOP jobs using `environment_mode =
"separate"`.
