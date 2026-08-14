# Third-party materials

| Material | Scope | License / provenance |
|---|---|---|
| scikit-learn `e27ccf58592fcfe8c7ca87f53dde840c436093b2` | Agent host source, pristine verifier host and exact-commit runtime wheel | BSD-3-Clause; upstream license texts remain in both source snapshots and wheel metadata. |
| imbalanced-learn `8504e95f0160f61d1b617ca66f779646d2ee609e` | Agent study source and read-only dynamic reference source | MIT; upstream `LICENSE` is retained in both snapshots. No donor code is copied into the Candidate implementation. |
| NumPy, SciPy, joblib, threadpoolctl, pytest and small Python dependencies | Checksum-locked environment wheels | Original wheel archives and their `.dist-info` license metadata are retained unmodified. Exact hashes are in each `wheels/SHA256SUMS`. |
| sklearn-compat 0.1.6 | Reference compatibility layer | BSD-3-Clause; original wheel retained unmodified and installed without dependency resolution for the document-locked development host. |
| Debian `libgomp1_12.2.0-14+deb12u1_amd64.deb` | OpenMP runtime for the locked host wheel | GCC Runtime Library Exception. Not redistributed here: image builds download the fixed URL, verify SHA256 `48fec46bda7f5b1638b9e959889bfbc20491247d402d120bb152687eb48143d7`, install it, and remove the archive. |
| `python:3.12.11-slim-bookworm` | Agent and verifier base image | Referenced by exact version tag; not stored in the repository. |

The clean-room Oracle is independently authored and marked BSD-3-Clause. The
Candidate runtime is created only after source scanning, and all donor and
reference materials are removed before Candidate import.
