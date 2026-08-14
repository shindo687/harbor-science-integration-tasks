# Validation baselines

- Oracle: clean-room bounded static nested sampler under `solution/`.
- NOP: unchanged locked Bilby tree.
- Near miss: `prior_mc.py`, a statistically plausible prior Monte Carlo
  estimator that sorts samples and exposes the API but never performs
  constrained live-point replacement or the nested evidence quadrature.

Direct verifier results:

| Baseline | Hidden points | Reward | Hard gates |
| --- | ---: | ---: | --- |
| Oracle native nested sampler | 15/15 | 1.0 | pass |
| Unchanged Bilby (NOP) | 0/15 | 0.0 | intentionally fails missing implementation |
| Prior-Monte-Carlo near miss | 4/15 | 0.266667 | pass |

The near miss passes API, isolation, and regression gates but fails all ten
core algorithm points plus the real workflow algorithm point. This demonstrates
that merely producing plausible evidence/posterior estimates does not solve the
constrained live-point and nested-quadrature task.

Evidence from direct and formal Harbor runs is stored under `evidence/`.

Formal Harbor 0.20 acceptance:

- Oracle job `algobridge-0030-oracle-r3`: one completed trial, zero errors,
  zero retries, Reward 1.0, 15/15; elapsed wall time about 77 seconds.
- NOP job `algobridge-0030-nop-r2`: one completed trial, zero errors, zero
  retries, Reward 0.0; elapsed wall time about 50 seconds.
- Both jobs used task checksum
  `92ae5bc85c5e66a215b5b5bd87044d9fb68ee77ef7dba29b0b0e59cfb3f5e0ec`
  and report the `/testbed` artifact as `status=ok`.
