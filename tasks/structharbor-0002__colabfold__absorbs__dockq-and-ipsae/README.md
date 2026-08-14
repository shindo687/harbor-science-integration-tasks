# ColabFold absorbs DockQ + ipSAE

Harbor 0.20 single-step algorithm-migration task. The Agent must independently
implement DockQ and ipSAE in locked ColabFold v1.6.1 and integrate both into the
same multi-model prediction post-processing path.

```text
Agent image                                  Separate verifier image
───────────                                  ───────────────────────
/testbed  locked ColabFold ──edit────┐       locked DockQ + locked ipSAE
/opt/dockq + /opt/ipsae  study source│ artifact      │ fresh references
/examples  5 public examples         └─────────────> │ delete both donors
                                                   │ UID 10001 candidate
                                                   └─ compare 15 cases
```

Only `/testbed` crosses the artifact boundary. Both phases use
`network_mode = "no-network"`; the verifier is a new container and starts only
after the Agent container has stopped.

## Locked sources and runtime

- ColabFold v1.6.1 commit
  `277662d7f4b0e4356c8d3fc4aec7c5a074cc65ad`, tree
  `3c473f8ce514a9d6836ae9381df26f1d6d3907d1`;
- DockQ commit `75db7ab4f6b824c70d120c5f620582e164ed5479`, tree
  `1d067a65cc2ce796a355fb8982ac5885ef996dab`;
- DunbrackLab/IPSAE commit
  `6174cf9e71cb1bd660cc805856a18c4871a6dec3`, tree
  `6c7e6e1c69d0150d7fd02d94593bd23387e9ebaa`;
- Python 3.12.11, NumPy 2.2.6, and Biopython 1.85;
- digest-pinned `python:3.12.11-slim-bookworm` base image and
  checksum-locked offline scientific wheels.

Exact identities, file-manifest hashes, licenses, and runtime hashes are in
`environment/source-lock.json`, `tests/reference-provenance.json`, and
`THIRD_PARTY.md`.

## Real differential reference

For every scientific case the verifier runs the locked original tools:

- DockQ imports its original `load_PDB` and
  `run_on_all_native_interfaces` implementation;
- ipSAE executes its original v4 AF2/PDB script and parses the emitted table.

References are generated dynamically from deterministic hidden structures,
PAE, pLDDT, and ipTM inputs. They are held only in verifier memory. Before the
candidate runs, the complete donor tree is deleted, `/tests` becomes unreadable,
and `/testbed` becomes root-owned/read-only. Candidate execution uses UID/GID
10001, has no donor import path, and cannot access the Agent's `/opt/dockq` or
`/opt/ipsae` trees.

## Scoring

The 15 equal points are:

| Points | Coverage |
| ---: | --- |
| 5 | DockQ: identity, ligand/interface distortion, rigid transform, automatic sequence-compatible chain swap, explicit mapping |
| 5 | ipSAE: asymmetric PAE, custom cutoffs, trimer/all pairs, and empty-under-cutoff behavior |
| 1 | Combined DockQ + ipSAE module CLI and strict standard JSON |
| 1 | Public signatures and ColabFold CLI flag contract |
| 3 | Real `predict_structure` body: multi-model scoring/ranking, summary and score JSON integration, directory native lookup, disabled/missing/error/single-chain states |

Numeric fields use absolute or relative tolerance `5e-4`. The locked ipSAE
reference writes a rounded human-readable table, which determines that
tolerance.

Compilation, dependency isolation, donor-vendoring detection, exact locked host
integrity, preservation of unrelated `batch.py` structure, and standard
ColabFold artifact regression are zero-reward hard gates. The source scanner
checks both `complex_metrics.py` and the modified `batch.py`, including full
file hashes and token-level partial-copy detection.

## Current validation

Direct final-container validation on 2026-08-14:

- public examples: `5/5`;
- Oracle: `15/15`, Reward `1.0`, all six hard gates passed;
- pristine NOP: `0/15`, Reward `0.0`;
- DockQ-only near miss: `7/15`, Reward `0.466666666667`;
- ipSAE-only near miss: `7/15`, Reward `0.466666666667`;
- maximum numeric absolute difference: `5e-4`.

Final Harbor 0.20 acceptance:

- Oracle: one trial, zero errors/retries, `15/15`, Reward `1.0`, 52 seconds;
- NOP: one trial, zero errors/retries, `0/15`, Reward `0.0`, 41 seconds;
- both trials used the same task checksum and collected `/testbed` with
  artifact status `ok`.

Machine-readable direct and Harbor reports are stored under
`validation/evidence/`.

## Run

```bash
harbor run --path . --agent oracle --n-concurrent 1 \
  --job-name structharbor-0002-oracle
harbor run --path . --agent nop --n-concurrent 1 \
  --job-name structharbor-0002-nop
```

Requirements: Linux x86_64, Docker or a Harbor-compatible backend, about 8 GB
RAM and 20 GB temporary storage. No GPU, model weights, MSA server, biological
database, or H200 host path is required. After cloning the repository and
obtaining the pinned base image, task image construction and execution require
no network.

Current state: `accepted`.
