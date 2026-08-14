# Third-party material

- **Wannier90** — official repository commit
  `e9f448e1ff4199ab5f983ec7265adca06b6363e8`, LGPL-2.1-or-later. The task
  archive contains the native source/build tree but omits large binary test and
  documentation assets.
- **TB2J** — official repository commit
  `4a0e33af8f73876fa895dd5bd83488aaef14b3f8` (version `0.9.19`), BSD-2-Clause.
  Its source is supplied read-only for study and separately to the verifier as
  the real reference. The requested answer must be a clean-room implementation
  and must not copy or depend on this package.
- **Python wheels** — their exact versions and hashes are pinned in
  `tests/wheels/SHA256SUMS`; they exist only in the root-only verifier reference
  environment. NumPy, SciPy, ASE, HamiltonIO, and TB2J dependencies provide the
  numerical runtime used by the original donor implementation.

The source archive boundaries and exact Git tree IDs are recorded in
`source-lock.json`.
