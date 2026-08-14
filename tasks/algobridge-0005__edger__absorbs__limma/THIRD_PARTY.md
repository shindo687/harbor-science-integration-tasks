# Third-party sources

This task carries byte-locked source archives solely to provide the host
checkout, the donor documentation/source visible to the agent, and an
independent runtime reference in the verifier.

| Component | Locked version | Role | License |
|---|---:|---|---|
| edgeR | 4.6.3 | host source | GPL (>= 2) |
| limma | 3.64.3 | donor/reference source | GPL (>= 2) |
| statmod | 1.5.0 | reference math dependency | GPL-2 or GPL-3 |
| R base image | 4.5.1 | runtime | GPL and image component licenses |

Exact repositories, commits, Git trees, archive digests and DESCRIPTION
digests are recorded in `source-lock.json`. The task solution must be an
independent implementation and is checked for long normalized fragments copied
from the locked limma/statmod sources.
