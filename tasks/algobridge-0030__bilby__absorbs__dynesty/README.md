# ALGOBRIDGE-0030: Bilby absorbs dynesty

This Harbor task asks an Agent to implement a native, bounded static nested
sampler in Bilby and remove the runtime dependency on dynesty for that path.

Status: `accepted`.

## Locked inputs

- Bilby: `a139afa5e0bb1879f18aed28344adec8ca6cab9b`
- dynesty: `d8affbcd18d1cb894e0c7102ba31c65794461b55`
- Host tree: `758065ac767be42b55d281eb37719e08dffb0b6b`
- Donor tree: `dbcfbfd8b9bd24bcc11dd3375b01832478030641`

The Agent receives the locked Bilby tree at `/testbed`, the donor study source
at `/opt/dynesty-source`, the task instruction, and five public examples. Only
`/testbed` is collected. A fresh verifier later runs original Bilby + original
dynesty for references, destroys private material, and evaluates the candidate
without network or dynesty.

## Acceptance result

| Run | Hidden points | Reward | Harbor trials / errors / retries |
| --- | ---: | ---: | ---: |
| Oracle | 15/15 | 1.0 | 1 / 0 / 0 |
| NOP (unchanged host) | 0/15 | 0.0 | 1 / 0 / 0 |
| Prior-Monte-Carlo near miss | 4/15 | 0.266667 | direct verifier |

The Oracle passes all six hard gates: locked-source integrity, locked original
Bilby→dynesty reference provenance, clean-room source scan, candidate runtime
isolation, API contract, and candidate-authored integration regression. Formal
Harbor Oracle and NOP runs have the same task checksum
`92ae5bc85c5e66a215b5b5bd87044d9fb68ee77ef7dba29b0b0e59cfb3f5e0ec`;
both `/testbed` artifacts were collected successfully.

The 15 independently scored points comprise ten statistical fixtures plus
prior reparameterization, deterministic stopping, scientific invariants, the
real string-selected Bilby workflow, and API/regression coverage. Original
dynesty produces fresh references before private source and expected values are
physically deleted; the candidate then runs as UID 10001 from a read-only tree.

## Layout and use

```text
instruction.md       Agent task contract
environment/         Agent image, locked sources, study donor, public examples
tests/               Separate offline verifier and locked reference runner
solution/            Author Oracle, not copied into either image
validation/          NOP/near-miss implementations and acceptance evidence
task.toml             Harbor isolation, resources, and /testbed artifact rule
```

Run the accepted checks with Harbor 0.20:

```bash
harbor run --path . --agent oracle --n-concurrent 1 --cpus ignore --memory ignore --yes
harbor run --path . --agent nop --n-concurrent 1 --cpus ignore --memory ignore --yes
```

The task is CPU-only: no H200, model weights, database, external service, or
host-path mount is required. Docker/Podman must have enough local space to hold
the pinned Python base image and approximately 200 MB of offline build context.
