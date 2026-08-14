# Third-party materials

This task embeds immutable source archives only for the locked host/reference
workflow and offline construction.

- GROMACS 2024.6 at commit
  `a7455395479a6eeebb8f5676ea580898c7662d21`, licensed under
  LGPL-2.1-or-later. The Agent modifies this host source tree.
- pymbar at commit `ed40ec3bbef03bb08938ad1a74d459b0d1ab81f7`,
  licensed under MIT. It is present only as the reference donor and is removed
  before candidate execution.
- NumPy, SciPy, and numexpr wheels are used only by the private reference
  runtime. Their exact hashes are in `source-lock.json` and
  `tests/wheels/SHA256SUMS`.
- CMake and Ninja wheels provide the locked offline build tools in both the
  Agent and verifier images. Their hashes are recorded in `source-lock.json`
  and the two wheel manifests.

The Oracle is a clean-room implementation written for this task. Candidate
source is checked for forbidden execution/dependency primitives and normalized
donor-source fragments before it is built.
