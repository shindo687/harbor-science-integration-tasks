# Third-party source material

## PDB2PQR 3.7.1

- Upstream: <https://github.com/Electrostatics/pdb2pqr>
- Role: host source tree presented at `/testbed`
- License: BSD 3-Clause

The snapshot contains all 208 ordinary tracked files from the exact release
commit.

## APBS 3.4.1

- Upstream: <https://github.com/Electrostatics/apbs>
- Role: donor documentation source and root-only LPBE reference executable
- License: BSD 3-Clause

The source snapshot contains all 1,404 ordinary tracked files. The recorded
`externals/pybind11` gitlink is not materialized. The official Linux release
archive is used only inside the protected verifier reference environment.

Candidate code must be a clean-room implementation and may not copy, import,
execute, or depend on APBS. Full provenance appears in
[`source-lock.json`](source-lock.json).
