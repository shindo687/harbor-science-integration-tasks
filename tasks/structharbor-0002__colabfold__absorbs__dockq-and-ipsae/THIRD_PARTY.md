# Third-party material

The task ships immutable source snapshots and runtime wheels for offline,
reproducible execution.

| Component | Locked identity | License | Task locations |
| --- | --- | --- | --- |
| ColabFold | v1.6.1, commit `277662d7f4b0e4356c8d3fc4aec7c5a074cc65ad` | MIT | `environment/host-source` |
| DockQ | commit `75db7ab4f6b824c70d120c5f620582e164ed5479` | MIT | Agent study source and verifier-private reference |
| DunbrackLab/IPSAE | commit `6174cf9e71cb1bd660cc805856a18c4871a6dec3` | MIT | Agent study source and verifier-private reference |
| NumPy | 2.2.6 | BSD-3-Clause | both offline wheelhouses |
| Biopython | 1.85 | Biopython License Agreement/BSD-style | both offline wheelhouses |

ColabFold's bundled OpenStructure data retains its upstream LGPL notice at
`environment/host-source/colabfold/openstructure/LGPL.txt`. The pinned Python
base image contains Debian and Python runtime components under their respective
upstream licenses.

The Agent may study donor source, but the submitted implementation must not
import, invoke, link, download, copy, or vendor either donor. The verifier runs
the original donor material only during its private reference phase and deletes
it before candidate execution.
