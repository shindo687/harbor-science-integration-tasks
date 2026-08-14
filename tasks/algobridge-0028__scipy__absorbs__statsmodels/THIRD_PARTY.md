# Third-party material

| Project/material | Role | Lock | License |
| --- | --- | --- | --- |
| SciPy | host source and exact wheel | commit `9506e3b773ccd043ae89be8f36154e9c0ce194d4` | BSD-3-Clause |
| statsmodels | donor source and exact reference wheel | commit `9062763c827da686a9b3117cffd2418d016a11e9` | BSD-3-Clause |
| NumPy, pandas, Patsy, pytest, Hypothesis and Python dependencies | offline runtime wheels | hashes in `wheels/SHA256SUMS` | their upstream licenses |
| Debian OpenBLAS, libgfortran, libgomp, libquadmath | exact offline runtime packages | hashes in `system-debs/SHA256SUMS` | Debian/upstream package licenses |

The Agent can read donor source for study, but donor source and the reference
wheel are absent from Candidate runtime. The Oracle is an independent
implementation of the published Huber IRLS equations and robust sandwich
covariance, not copied donor code.

`source-lock.json` records the root commits, every SciPy submodule commit,
exact wheel hashes, base image ID, runtime versions, and fixture hashes.

