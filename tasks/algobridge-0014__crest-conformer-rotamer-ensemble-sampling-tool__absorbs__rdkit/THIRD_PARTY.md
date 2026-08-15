# Third-party source material

## CREST 3.0.2

- Upstream: <https://github.com/crest-lab/crest>
- Role: host source tree presented at `/testbed`
- License: GNU Lesser General Public License 3.0

The snapshot contains all 277 ordinary tracked files. Six upstream gitlink
submodules are identified by the exact host Git tree but are not materialized;
the bounded task neither builds nor depends on them.

## RDKit 2026.03.5

- Upstream: <https://github.com/rdkit/rdkit>
- Role: donor documentation source and root-only native ETKDG reference
- License: BSD 3-Clause

Candidate code must be a clean-room implementation and may not copy, import, or
depend on RDKit. Full provenance appears in [`source-lock.json`](source-lock.json).
