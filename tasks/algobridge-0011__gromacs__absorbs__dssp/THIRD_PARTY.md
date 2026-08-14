# Third-party material

- **GROMACS** — official GitLab tag `v2024.6`, commit
  `a7455395479a6eeebb8f5676ea580898c7662d21`, LGPL-2.1-or-later.
- **DSSP** — official PDB-REDO repository version `4.4.11`, commit
  `3cbec3abea5169ea8fac030d0e43d28102b128aa`, BSD-2-Clause.
- **Reference executable** — conda-forge `dssp 4.4.11 h629725b_0`,
  BSD-2-Clause. The original package and a prefix-relocated offline runtime are
  preserved in the verifier context.
- **Structural fixtures** — RCSB PDB entries 1CRN, 1ZDD, and 1TEN; exact
  source hashes are locked.
- **CMake and Ninja** — offline PyPI wheels used only to build GROMACS.

Exact commits, Git trees, archive hashes, runtime hashes, and image digest are
recorded in `source-lock.json`.
