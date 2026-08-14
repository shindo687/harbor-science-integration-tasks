# Third-party material

- **OpenMM** — official repository tag `8.4.0`, commit
  `47684368dbbe4185d068be77d32a962059cfc37c`, under the licenses documented
  by OpenMM (MIT/LGPL components). All 2,214 tracked files are archived.
- **AutoDock Vina** — official CCSB-Scripps repository tag `v1.2.7`, commit
  `8eb40404f4f45608acb3b01427587ac049f27c1f`, Apache-2.0. All 308 tracked
  files are archived and will be available as read-only donor documentation.
- **Reference adapter** — a 32 KiB x86-64 executable compiled from
  `tests/reference_adapter.cpp`; it calls the locked donor potential classes
  directly. Three minimal compatibility headers replace only unused Boost
  declarations so the adapter does not need a Boost installation. The build
  script, compiler flags, executable hash, and protocol are locked.

Exact repositories, Git trees, archive hashes, file counts, and runtime
provenance are recorded in `source-lock.json`.
