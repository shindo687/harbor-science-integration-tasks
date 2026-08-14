# SciPy absorbs statsmodels Huber RLM

Harbor single-step algorithm-migration task materialized from
`ALGOBRIDGE-0028` in the WorkflowFeatureBench design document.

The Agent receives exact locked SciPy source at `/testbed`, exact locked
statsmodels source at `/opt/statsmodels-source`, five public examples, and no
network. It must add native `scipy.stats.robust_linear_model`; only `/testbed`
is transferred to an isolated verifier. The Candidate cannot import, invoke,
link, download, or vendor statsmodels.

## Locked sources

- SciPy `9506e3b773ccd043ae89be8f36154e9c0ce194d4`, including all eight
  commit-locked submodules;
- statsmodels `9062763c827da686a9b3117cffd2418d016a11e9`;
- Python 3.12.11 and NumPy 2.5.2;
- locally built exact wheels, hashes in `source-lock.json` and each
  `wheels/SHA256SUMS`.

The reference is the real original pipeline: arrays and positive integer
frequency weights are expanded, then passed to locked
`statsmodels.robust.robust_linear_model.RLM` with `HuberT`. It supports MAD and
Huber proposal 2 scale plus H1/H2/H3 robust covariance. There is no fake data
pipeline or reimplemented reference.

SciPy contains compiled extensions. Agent development and verifier execution
therefore overlay changed `/testbed/scipy/**/*.py` files on the wheel built
from the identical locked commit. Candidate `.so` files are excluded from the
artifact and rejected by the source scan. Before Candidate execution, the
reference venv, wheelhouse, pristine source, and materialization tool are
deleted; `/testbed` and the runtime become root-owned/read-only, and the
Candidate runs as UID 10001 without network access.

## Scoring

The verifier awards 15 equal points:

| Points | Coverage |
| ---: | --- |
| 12 | Dynamic differentials: intercept/no intercept, MAD/Huber scale, H1/H2/H3 covariance, positive/negative outliers, high leverage, integer frequency weights, rank deficiency, near-zero scale, alternate threshold, and a bounded non-converged fit |
| 1 | Converged fits satisfy the Huber estimating equation |
| 1 | Response-unit equivariance and clean-data agreement with OLS |
| 1 | Public API/error contract, clean-room isolation, and SciPy host regression |

Parameters, scale, weights, residuals, and finite iteration history use
absolute/relative tolerance `1e-8`; covariance uses `1e-6`.

## Acceptance

Direct-container validation on 2026-08-14:

- Oracle: `15/15`, Reward `1.0`;
- pristine NOP: `0/15`;
- OLS-only near miss: `0/15`;
- public examples: `5/5`;
- selected untouched SciPy stats regression: `222 passed`;
- maximum parameter and covariance absolute errors across the dynamic cases:
  `1.56e-15` and `2.78e-17`, respectively.

Final Harbor 0.20 acceptance:

- Oracle: 1 trial, 0 exceptions, `15/15`, Reward `1.0`, 1 minute 54 seconds;
- NOP: 1 trial, 0 exceptions, `0/15`, Reward `0.0`, 1 minute 34 seconds.

Machine-readable direct and Harbor reports are in `validation/evidence/`.

## Run with Harbor

```bash
harbor run -p . -a oracle -n 1 --job-name algobridge-0028-oracle
harbor run -p . -a nop -n 1 --job-name algobridge-0028-nop
```

Requirements: Linux x86_64, Docker or a Harbor-compatible backend, and roughly
16 GB RAM plus 30 GB temporary storage. No GPU is required. Runtime and image
construction are fully offline after the repository and pinned Python base
image are available; Python wheels and Debian OpenBLAS/Fortran packages are
checksum-locked in the task.

Current state: `accepted`.

