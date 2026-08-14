# Third-party material

- **AlphaFold2** — official Google DeepMind repository commit
  `c77e5d2a8961d1a353632c462914ff0a32a950f6`, Apache-2.0. The task archives
  all 121 tracked files at that commit; model parameters are not included.
- **DSSP** — official PDB-REDO repository `v4.4.11` commit
  `3cbec3abea5169ea8fac030d0e43d28102b128aa`, BSD-2-Clause. Its complete 32
  tracked files are supplied as read-only algorithm documentation.
- **Reference executable** — conda-forge `dssp 4.4.11 h629725b_0`,
  BSD-2-Clause. The original `.conda` package and its license are preserved.
  The verifier runtime replaces each complete conda prefix field with
  `/opt/dssp`, retains the compiled `/share/libcifpp` and
  `/var/cache/libcifpp` suffixes, and NUL-pads the remaining bytes.
- **Chemical Component Dictionary subset** — the 20 standard amino-acid CCD
  records from RCSB are concatenated into the verifier's offline
  `components.cif`; its exact SHA-256 is locked.
- **Structural fixtures** — RCSB PDB entries 1CRN, 1ZDD, and 1TEN. Their
  original downloads and SHA-256 values are recorded in `source-lock.json`.
- **NumPy** — PyPI wheel 2.3.3 for CPython 3.13, BSD-3-Clause. The exact wheel
  URL and SHA-256 are locked and the wheel is installed without network access.

Exact repositories, Git trees, package URLs, hashes, file counts, and base
image digest are recorded in `source-lock.json`.
