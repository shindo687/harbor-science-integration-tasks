# NetworkX absorbs scikit-learn spectral clustering

Harbor single-step algorithm-migration task, materialized from
`ALGOBRIDGE-0029` in the benchmark design document.

The Agent receives the exact locked NetworkX host source in `/testbed`, the
exact locked scikit-learn donor source for study in `/opt/scikit-learn`, five
public examples, and no network.  Only `/testbed` is transferred to a separate
verifier.  The verifier dynamically runs the original NetworkX → scikit-learn
pipeline, removes the donor, runs the candidate as an unprivileged user, and
compares partitions, spectral subspaces, normalized-cut values, invariants,
and host regressions.

## Locked sources

- NetworkX: `30bfe1b2c32afa8d3abdc4d2a10bcacd33b3dce5`
- scikit-learn: `e27ccf58592fcfe8c7ca87f53dde840c436093b2`
- Python: 3.12
- NumPy: 2.3.2
- SciPy: 1.16.1
- scikit-learn wheel: built locally from the locked commit; its checksum is
  recorded in `tests/wheels/SHA256SUMS`.

The locked NetworkX commit stores `benchmarks/pyproject.toml` as a malformed
symlink target ending in a newline.  Both host snapshots materialize that one
path as a regular copy of the root `pyproject.toml`; the exact path, reason,
and resulting SHA256 are recorded in `environment/source-lock.json`.  No
runtime source file is changed by this packaging normalization.

## Acceptance gates

- `NOP = 0` and the bundled Oracle solution reaches `1.0`.
- A representative near-miss does not reach `1.0`.
- Candidate runtime has no scikit-learn package, executable, source, network,
  or access to verifier-private files.
- Partition comparison is label-permutation invariant.
- Spectral projector tolerance is `1e-6`; normalized-cut tolerance is `1e-8`.
- Label renaming, node insertion order, and disconnected-component invariants
  are checked independently of the differential cases.
- Existing NetworkX tests covering the touched package must still pass.

## Scoring

The verifier awards 15 equal points:

| Points | Coverage |
|---:|---|
| 12 | Differential fixtures: two moons, weighted SBM, disconnected graph, isolates, weighted ties, degenerate eigenspace, heterogeneous degrees, weighted path, ring of cliques, weighted grid, barbell, and four weighted blocks |
| 1 | Node insertion-order invariance |
| 1 | Disconnected components are not split or mixed when `k` is sufficient |
| 1 | API error contract plus 198 existing NetworkX community/Laplacian tests |

Every differential point requires all of: ARI `1.0`, spectral projector error
at most `1e-6`, eigenvalue error at most `1e-8`, and normalized-cut error at
most `1e-8`.

## Clean-room execution order

```text
locked pristine NetworkX + locked scikit-learn wheel
                       │ dynamic reference results
                       ▼
delete reference venv + pristine host + complete wheelhouse
                       │
chown/chmod transferred /testbed read-only to candidate
                       │
                       ▼
UID 10001 candidate NetworkX, no network, private paths inaccessible
                       │
                       ▼
partition + eigenspace + eigenvalues + ncut + invariants + regressions
```

The candidate runner is a real import/call path into the modified NetworkX;
there is no fake graph, fake estimator, or mocked pipeline.

## Author validation

Final direct-container validation on 2026-08-13:

- Oracle: `15/15`, Reward `1.0`, all 8 hard gates passed;
- pristine NetworkX (NOP): `0/15`, Reward `0.0`;
- deterministic-label/zero-spectrum near-miss: `2/15`, Reward `0.133333`;
- public examples: `5/5`;
- touched host regression scope: `198 passed`.

The Oracle's largest observed spectral-projector error was approximately
`7.4e-11`, below the `1e-6` tolerance.  Full machine-readable reports are in
`validation/evidence/`.

Final Harbor 0.20 acceptance on 2026-08-13:

- Oracle: 1 trial, 0 exceptions, `15/15`, Reward `1.0`, 1 minute 28 seconds;
- NOP: 1 trial, 0 exceptions, `0/15`, Reward `0.0`, 1 minute 21 seconds.

The first attempted Oracle build is intentionally not counted: this host's
Docker registry mirror returned HTTP 401 before creating the Agent container.
After loading the pinned base image into the local Docker store, the complete
Harbor trial above passed without retries or exceptions.

## Run with Harbor

```bash
harbor run -p . -a oracle -n 1 --job-name algobridge-0029-oracle
harbor run -p . -a nop -n 1 --job-name algobridge-0029-nop
```

The task requires Linux x86_64, Docker or a Harbor-compatible container
backend, and no GPU.  Agent and verifier runtime are `no-network`; Python
wheels are included with checksums.  During verifier image construction, the
fixed Debian OpenMP package required by the locked donor is downloaded and
SHA256-verified, then its package file is deleted.  Therefore the base
`python:3.12.11-slim-bookworm` image and that Debian package must be present in
the build cache or fetchable during the image-build phase.  See
`THIRD_PARTY.md` for the source and dependency license inventory.
