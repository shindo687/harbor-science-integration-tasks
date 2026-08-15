# Locked hap.py reference build

The `xcmp`, `bgzip`, and `tabix` executables were built from the complete
Illumina hap.py `v0.3.15` source lock recorded in `source-lock.json`.

`xcmp-build-compat.patch` records the only source changes used for the build:

- disable unused Boost bzip2 support because the build host has no bzip2
  development headers; xcmp does not use that component;
- include the standard `<limits>` header explicitly for modern GCC.

The donor checkout was restored and verified clean after the build. The patch
does not change haplotype comparison, VCF parsing, or quantification behavior.
The runtime hashes in `source-lock.json` authenticate the exact executables.
