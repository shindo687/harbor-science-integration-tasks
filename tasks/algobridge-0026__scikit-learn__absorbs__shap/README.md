# scikit-learn absorbs SHAP TreeSHAP

Harbor single-step algorithm-migration task materialized from
`ALGOBRIDGE-0026` in the WorkflowFeatureBench design document.

The Agent receives exact locked scikit-learn source at `/testbed`, an
algorithm-relevant locked SHAP source snapshot at `/opt/shap-source`, five
public examples, and no network. It must add native
`sklearn.inspection.tree_shap`; only `/testbed/sklearn` is transferred to a
separate verifier. The Candidate cannot import, invoke, link, download, or
vendor SHAP.

## Locked sources

- scikit-learn commit `e27ccf58592fcfe8c7ca87f53dde840c436093b2`, tree
  `87223e64df8880951bc88ee6049a8bf453dccf88`;
- SHAP commit `df974a1966294b9c7acebb1373fd6dc5445d1d3d`, tree
  `4ec180cdefa828142ec4e6da5c2b0c80697bf8e8`;
- reference SHAP wheel SHA-256
  `0321cb5f92a235af58982a9d36c58634125764cc10d0298fff6742c8c4465165`;
- Python 3.12.11, NumPy 2.3.2, and SciPy 1.16.1.

The full identities, snapshot scope, and wheel provenance are recorded in
`source-lock.json`; every offline wheelhouse also has a `SHA256SUMS` manifest.
The verifier independently checks source hashes, both locked commit/tree
identities, the donor build identity, and the SHAP wheel digest.

## Reference and isolation

The reference is the real original pipeline: deterministic fresh models are
trained with the locked scikit-learn wheel and explained by locked
`shap.TreeExplainer(feature_perturbation="tree_path_dependent",
model_output="raw")`. There is no fake runner, cached hidden output, or
reimplemented reference.

After computing references, the verifier deletes the SHAP venv, donor source,
wheelhouses, pristine host source, reference runner, and materialization tool.
It overlays only changed Python source on the locked scikit-learn wheel, makes
the Candidate trees root-owned/read-only, and evaluates as UID 10001. The
verifier directory is unreadable to that user and networking is disabled by
Harbor.

## Scoring

The verifier awards 15 equal points:

| Points | Coverage |
| ---: | --- |
| 13 | Fresh differential models: weighted and multi-output trees, ordered and multi-output forests, regression/binary/multiclass outputs, gradient boosting raw outputs, missing-value branches, repeated deep thresholds, unused features, and DataFrame input |
| 1 | Scientific invariants: exact local accuracy, exact zero for unused features, and boosting-tree linearity |
| 1 | Public API/error contract, dependency isolation, clean-room source scan, and focused plus upstream tree regressions |

`values`, `base_values`, and raw `predictions` are compared at absolute and
relative tolerance `1e-9`. Supported output selectors, shapes, estimator order,
and rejection of unsupported sparse/categorical/multiclass-boosting cases are
part of the contract.

## Acceptance

Final acceptance evidence is machine-readable under `validation/evidence/`:

- public examples: `5/5`;
- direct and Harbor Oracle: `15/15`, Reward `1.0`;
- pristine NOP: `0/15`, Reward `0.0`;
- intentionally inexact single-path/Saabas near miss: `2/15`, Reward
  `0.133333333333`;
- relevant host regressions: `580 passed`, `7 skipped`;
- maximum Oracle absolute error: values `1.78e-15`, base values `1.95e-16`,
  predictions `0`;
- Harbor Oracle and NOP: one completed trial each, zero verifier errors and
  zero retries.

The near miss passes the same packaging, API, isolation, and host-regression
gates but fails all 13 exact differential cases, showing that the grader
discriminates a plausible path approximation from exact TreeSHAP.

## Run with Harbor

```bash
harbor run --path . --agent oracle --n-concurrent 1 \
  --job-name algobridge-0026-oracle
harbor run --path . --agent nop --n-concurrent 1 \
  --job-name algobridge-0026-nop
```

Requirements: Linux x86_64, Docker or a Harbor-compatible backend, and roughly
8 GB RAM plus 20 GB temporary storage. No GPU is required. Python execution is
fully offline after the repository and pinned `python:3.12.11-slim-bookworm`
base image are available. Image construction currently downloads one
checksum-locked Debian `libgomp1` package, so a cold build needs that URL
reachable or the package mirrored locally.

Current state: `accepted`.
