# ALGOBRIDGE-0006 — Scanpy absorbs scIB LISI

Harbor single-step algorithm-migration task materialized from `ALGOBRIDGE-0006`
in the WorkflowFeatureBench design document. An Agent receives locked Scanpy
source at `/testbed`, locked scIB source at `/opt/scib-source`, five public
examples, and no network. It must add native `scanpy.metrics.lisi_graph_score`
without importing, executing, linking, downloading, or vendoring scIB at
Candidate runtime.

## Locked sources

- Scanpy: `fabadb9412c0d1cd9df9d9c2e95ac266d564ee18`
- scIB: `cd67913396b4c0430710b3d90f1d1841f5fa4468`
- Python 3.12.11, Scanpy `1.14.0.dev21+gfabadb941`, scIB `1.1.7`;
- all 67 Python wheels are repository-carried and checksum-locked by
  `environment/wheels/SHA256SUMS` and `tests/wheels/SHA256SUMS`.

The verifier runs the original scIB `lisi_graph_py` path, including its compiled
`knn_graph.cpp` shortest-path executable and its Python perplexity/Simpson
calculation, to obtain reference values.  It then removes all reference and
donor material before running the modified Scanpy as an unprivileged user.

## Isolation and scoring

Only `/testbed` is transferred from the Agent container into the separate
verifier container. The verifier first computes dynamic hidden references with
real locked scIB. Before Candidate execution it deletes the reference venv,
donor/pristine sources, wheelhouse, and materialization tools; locks Candidate
files read-only; makes `/tests` unreadable; and runs Candidate as UID 10001.
The report explicitly verifies that scIB cannot be imported.

The verifier awards 15 equal points over deterministic hidden graphs covering
mixed/separated populations, disconnected components, isolates, unbalanced
categories, repeated distances, weighted graphs, and low/high perplexity. It
compares per-cell iLISI/cLISI within `1e-6`, medians within `1e-7`, and exact
effective-neighbor counts. API/error checks, label-renaming and CSR-order
invariants, single-category behavior, and selected unchanged Scanpy metrics
tests are mandatory gates.

## Acceptance

Final direct-container validation on 2026-08-14:

- clean-room Oracle: `15/15`, Reward `1.0`;
- pristine NOP: `0/15`;
- uniform-probability near miss: `0/15`, while API/regression and scientific
  invariant gates pass;
- public examples: `5/5`;
- selected Scanpy regression: `12 passed` (four parameterized test targets);
- maximum hidden-case absolute error: `3.55e-15`.

Final Harbor 0.20 acceptance:

- Oracle: 1 trial, 0 exceptions, `15/15`, Reward `1.0`, 1 minute 35 seconds;
- NOP: 1 trial, 0 exceptions, `0/15`, Reward `0.0`, 43 seconds.

Machine-readable reports are in `validation/evidence/`.

## Run with Harbor

```bash
harbor run -p . -a oracle -n 1 --job-name algobridge-0006-oracle
harbor run -p . -a nop -n 1 --job-name algobridge-0006-nop
```

Requirements: Linux x86_64, Docker or a Harbor-compatible container backend,
roughly 16 GB RAM and 30 GB temporary storage. No GPU or H200-local bind mount
is required. Builds and trials are fully offline after the repository and the
pinned `python:3.12.11-slim-bookworm` base image are available. On a rootless
backend without cgroups, add `--cpus ignore --memory ignore`; normal Docker does
not need those flags.

Current state: `accepted`.
