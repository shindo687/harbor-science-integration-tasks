# Third-party source material

This task carries complete, immutable source snapshots for offline execution
and provenance verification.

## AutoDock Vina 1.2.7

- Upstream: <https://github.com/ccsb-scripps/AutoDock-Vina>
- Role: host source tree presented at `/testbed`
- License: Apache License 2.0 (`LICENSE` in the snapshot)

## RDKit 2026.03.5

- Upstream: <https://github.com/rdkit/rdkit>
- Role: donor documentation source and root-only native reference runtime
- License: BSD 3-Clause (`license.txt` in the snapshot)

The exact commits, trees, archive hashes, wheel hashes, and immutable base image
digest are recorded in [`source-lock.json`](source-lock.json). Candidate code
must be a clean-room implementation and may not copy or depend on RDKit.
