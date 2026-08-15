# Third-party provenance and licenses

## HH-suite / HHblits host

- Repository: <https://github.com/soedinglab/hh-suite>
- Commit: `43095e46ada4ec2a8a47d47ef5ad7e38b1429f7b`
- License in the locked repository: GNU GPL version 3 (`GPL-3.0-only`)
- License file SHA-256:
  `589ed823e9a84c56feb95ac58e7cf384626b9cbf4fda2a907bc36e103de1bad2`

The complete locked host tree and its license are included in
`environment/source/host-source.tar.gz` and `tests/source/host-source.tar.gz`.

## CCMpred scientific oracle

- Repository: <https://github.com/soedinglab/CCMpred>
- Commit: `2919b9c9ae976f73bc4dbb67908170afc3578da8`
- Published license: GNU Affero GPL version 3 or later
  (`AGPL-3.0-or-later`)
- License file SHA-256:
  `57c8ff33c9c0cfc3ef00e650a1cc910d7ee479a8bc509f6c9209a7c2a11399d6`

The locked build uses CCMpred's pinned `libconjugrad` submodule at commit
`e503ee8a1e1d392339a1cd3ddd540468fe896cd1`. That submodule commit does not
carry a separate license file; it is preserved as the exact build dependency
of the CCMpred source distribution under CCMpred's published project notice.
The combined source needed to reproduce the reference binary is included in
both copies of `donor-source.tar.gz`.

The root-only reference executable was built from that source in deterministic
CPU-only, double-precision mode. A 415-byte compatibility patch only moves the
standard `<math.h>` include before an old macro header so the historical
optimizer compiles on GCC 11; it does not change executable statements or
numeric behavior. The patch is included beside the verifier binary.

CCMpred source and the reference executable are verifier assets. Submitted
HH-suite code must be an independent implementation and may not link, execute,
load, vendor, or require CCMpred or `libconjugrad`.
