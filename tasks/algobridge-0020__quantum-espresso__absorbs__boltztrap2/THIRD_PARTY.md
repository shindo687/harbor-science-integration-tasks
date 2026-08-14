# Third-party source locks

This task redistributes byte-reproducible `git archive` snapshots solely to
provide the upstream development tree and the isolated reference
implementation used by the verifier.

| Role | Project | Locked revision | License | Upstream |
|---|---|---|---|---|
| Host | Quantum ESPRESSO 7.5 | `770a0b2d12928a67048e2f3da8d10d057e52179e` | GPL-2.0-or-later | https://github.com/QEF/q-e |
| Reference donor | BoltzTraP2 25.3.1 | `8d9fc2534642718c26ee35a03f9eac39d8431eb2` | GPL-3.0-or-later | https://gitlab.com/sousaw/BoltzTraP2 |

The candidate must be a clean-room implementation inside the host tree. The
donor source and runtime are reference-only and are unavailable while the
candidate is executed.

