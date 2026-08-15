# Third-party provenance

## Host: GATK 4.6.2.0

- Repository: https://github.com/broadinstitute/gatk
- Locked commit/tree: recorded in `source-lock.json`
- License: Apache License 2.0 (`LICENSE.TXT` in the locked tree)

The planning document labeled the host BSD-3-Clause. The official locked GATK
source is Apache-2.0, so this task records the source's actual license rather
than copying the inconsistent planning metadata.

## Donor/oracle: hap.py 0.3.15

- Repository: https://github.com/Illumina/hap.py
- Locked commit/tree: recorded in `source-lock.json`
- License: BSD-2-Clause (`LICENSE.txt` in the locked tree)

The donor source is exposed only for documentation. The verifier's `xcmp`,
`bgzip`, and `tabix` executables are root-only, hash-locked reference assets.
The two build-portability changes are fully captured by
`tests/reference-bin/xcmp-build-compat.patch`; they do not change comparison
semantics.

## Container runtimes

The Python and Eclipse Temurin images are pinned by immutable OCI digests in
`source-lock.json` and the Dockerfiles.
