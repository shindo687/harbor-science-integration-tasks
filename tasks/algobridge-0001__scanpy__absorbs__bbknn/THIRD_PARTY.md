# Third-party source provenance

The repository contains immutable source snapshots for authoring and differential verification.

| Role | Project | Commit | License | Snapshot |
|---|---|---|---|---|
| Host | Scanpy | `fabadb9412c0d1cd9df9d9c2e95ac266d564ee18` | BSD-3-Clause | `environment/host-source` |
| Donor | BBKNN | `95ce34b8905cbde307704a77436c354938ba0367` | MIT | `environment/donor-source` |

The snapshots retain their upstream license files. The intended solution is a clean-room Scanpy
implementation and must not copy or import the donor implementation at runtime.
