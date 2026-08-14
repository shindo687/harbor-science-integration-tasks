# Validation

The committed evidence is generated from the same verifier image used by the
task.  The direct controls establish three distinct behaviors:

| Candidate | Hard gates | Hidden cases | Reward |
| --- | --- | ---: | ---: |
| clean-room Oracle | pass | 15/15 | 1.0 |
| pristine FastTree (NOP) | source-policy rejection | 0/15 | 0.0 |
| sequential-merge near miss | pass | 5/15 | 0.333333333333 |

The near miss retains the CLI, affine DP, profile merge, final FastTree call,
and all isolation/legacy gates, but deliberately ignores pair distances when
choosing guide-tree merges.  Its partial result demonstrates that the hidden
cases distinguish the requested UPGMA algorithm from a plausible shortcut.

`direct-oracle-report.json`, `direct-nop-report.json`, and
`direct-sequential-near-miss-report.json` are complete machine-readable grader
reports.  `public-examples.txt` records the independent five-example check.

## Formal Harbor acceptance

- Oracle: one completed trial, zero errors/retries, `15/15`, Reward `1.0`;
- NOP: one completed trial, zero errors/retries, Reward `0.0`;
- both job locks contain task digest
  `sha256:f584aef7dd74c315886601d054e8aec3f951c954316949f8de051b5a586c0cf0`;
- both artifact manifests record `/testbed` as `ok`.

The `harbor-{oracle,nop}-job-*`, `trial-*`, `artifact-manifest`, and
`verifier-report` files are copied verbatim from those formal runs.
