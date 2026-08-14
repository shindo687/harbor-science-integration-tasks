# Third-party materials

This task contains exact, locked upstream materials for reproducible and
clean-room differential evaluation.

| Material | Scope | License / provenance |
|---|---|---|
| NetworkX `30bfe1b2c32afa8d3abdc4d2a10bcacd33b3dce5` | Agent host source and pristine verifier host | BSD-3-Clause; the upstream text is retained as `LICENSE.txt` in both snapshots. |
| scikit-learn `e27ccf58592fcfe8c7ca87f53dde840c436093b2` | Donor source visible to the Agent and a locally built reference-only wheel | BSD-3-Clause; the upstream `COPYING` file is retained with the donor source. |
| NumPy, SciPy, joblib, threadpoolctl, pytest and their small Python dependencies | Checksum-locked wheels used to build the two environments | The original wheel archives and their `.dist-info` license metadata are retained unmodified. Exact filenames and hashes are in each `wheels/SHA256SUMS`. |
| Debian `libgomp1_12.2.0-14+deb12u1_amd64.deb` | OpenMP runtime needed only by the locked reference wheel | GCC Runtime Library Exception. The package is not redistributed in this repository: the verifier image build downloads the fixed URL, verifies SHA256 `48fec46bda7f5b1638b9e959889bfbc20491247d402d120bb152687eb48143d7`, installs it, and removes the archive. |
| `python:3.12.11-slim-bookworm` | Agent and verifier base image | Referenced by immutable version tag; not stored in the repository. |

The candidate is evaluated only after the scikit-learn reference environment,
pristine reference host and complete verifier wheelhouse have been removed.
No donor code or binary is copied into the submitted NetworkX tree.
