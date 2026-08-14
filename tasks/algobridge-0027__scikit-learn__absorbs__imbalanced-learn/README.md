# scikit-learn absorbs imbalanced-learn SMOTE

Harbor single-step algorithm-migration task materialized from
`ALGOBRIDGE-0027` in the WorkflowFeatureBench design document.

The Agent receives the exact locked scikit-learn host source in `/testbed`,
the exact locked imbalanced-learn donor source in `/opt/imbalanced-learn`, five
public examples, and no network. Only `/testbed` is transferred to a separate
verifier. The final Candidate must provide native deterministic SMOTE without
importing, calling, linking, downloading, or vendoring imbalanced-learn.

## Locked sources

- scikit-learn: `e27ccf58592fcfe8c7ca87f53dde840c436093b2`
- imbalanced-learn: `8504e95f0160f61d1b617ca66f779646d2ee609e`
- Python: 3.12
- NumPy: 2.3.2
- SciPy: 1.16.1
- locally built exact-commit scikit-learn wheel: hash in each
  `wheels/SHA256SUMS`

The locked imbalanced-learn development commit has incomplete wheel package
discovery metadata, so the reference imports its complete read-only source
snapshot directly. This preserves the exact commit instead of silently
patching donor packaging. `sklearn-compat` is installed from its locked wheel
without dependency resolution because its published metadata caps
scikit-learn below the document-locked `1.10.dev0`; the real reference import
and SMOTE execution are tested during image validation.

The scikit-learn host contains compiled extensions. Agent-side development and
verifier execution therefore materialize changed `/testbed/sklearn/**/*.py`
files over the wheel built from the identical locked host commit. Compiled
artifacts are never accepted from the Agent and are excluded from transferred
artifacts.

## Acceptance gates

- dynamic locked scikit-learn → imbalanced-learn reference;
- exact fixed-seed synthetic samples plus parent/neighbor/lambda provenance;
- interpolated sample-weight lineage;
- independent segment, target-count, input-prefix, determinism and tie checks;
- donor/reference/wheelhouse removal before unprivileged Candidate execution;
- forbidden dependency scan and scikit-learn host regression;
- `NOP = 0`, Oracle `= 1`, representative near-miss `= 0`;
- all existing tests in the touched scikit-learn preprocessing package pass.

## Scoring

The verifier awards 15 equal points:

| Points | Coverage |
|---:|---|
| 12 | Dynamic differential fixtures: binary/multiclass strategies, target dictionaries, string labels, duplicate points, equidistant ties, float32, sample weights, binary ratio, all-classes mode, and high-dimensional input |
| 1 | Every synthetic row lies on its reported same-class parent-neighbor segment and every propagated weight uses the same lambda |
| 1 | Reference-derived class counts, unchanged input prefix, deterministic rerun and tie behavior |
| 1 | API/error contract plus all existing scikit-learn preprocessing tests |

Each differential point requires exact labels, dtypes, class strategy and
parent/neighbor provenance; synthetic values and propagated weights use
absolute tolerance `1e-12`, while RNG lambda values use `1e-15`.

## Clean-room execution order

```text
locked scikit-learn wheel + locked imbalanced-learn source
                          │ dynamic reference + traced provenance
                          ▼
scan only Agent-changed files; reject donor/verifier references and binaries
                          │
overlay changed host Python onto the identical locked host wheel
                          │
delete donor source + reference venv + pristine host + complete wheelhouse
                          │
lock /testbed and runtime root-owned/read-only
                          │
                          ▼
UID 10001 Candidate, private verifier paths unreadable, no network
```

The reference trace wraps the original donor's `_generate_samples` call to
observe the actual parent row, selected neighbor and lambda; it does not use a
fake sampler or reproduce donor output in the verifier.

## Author validation

Final direct-container validation on 2026-08-13:

- Oracle: `15/15`, Reward `1.0`, all hard gates passed;
- pristine scikit-learn (NOP): `0/15`, Reward `0.0`;
- API-only no-resampling near-miss: `0/15`, Reward `0.0`;
- public examples: `5/5`;
- touched host regression: `1548 passed`, `789 skipped`.

Across all 12 hidden differential cases, the Oracle's observed maximum error
for synthetic values, lambdas and propagated weights was exactly `0.0`.
Machine-readable reports are in `validation/evidence/`.

Final Harbor 0.20 acceptance on 2026-08-13:

- Oracle: 1 trial, 0 exceptions, `15/15`, Reward `1.0`, 1 minute 17 seconds;
- NOP: 1 trial, 0 exceptions, `0/15`, Reward `0.0`, 52 seconds.

## Run with Harbor

```bash
harbor run -p . -a oracle -n 1 --job-name algobridge-0027-oracle
harbor run -p . -a nop -n 1 --job-name algobridge-0027-nop
```

The task requires Linux x86_64, Docker or a Harbor-compatible backend, and no
GPU. Agent and verifier runtime are `no-network`; checksum-locked Python
wheels are included. During image construction, a fixed Debian OpenMP runtime
is downloaded and SHA256-verified, so the base image and that package must be
cached or fetchable during the build phase. See `THIRD_PARTY.md`.

Current state: `accepted`.
