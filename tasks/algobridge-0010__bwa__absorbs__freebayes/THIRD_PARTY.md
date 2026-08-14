# Third-party source provenance

## Host: BWA

- Repository: <https://github.com/lh3/bwa>
- Version: 0.7.17
- Commit: `9f26bfcc7780753129b60717ecab0ebba6f04b7c`
- License: GPL-3.0-only (`COPYING` in the source archive)

## Donor: FreeBayes

- Repository: <https://github.com/freebayes/freebayes>
- Version: 1.3.6
- Commit: `084dce52e54af5adbd1e2b0a67f3733dd8bfddc0`
- License: MIT (`LICENSE` in the source archive)

The donor archive includes the exact recursive submodules recorded in
`source-lock.json`, including htslib, htscodecs, vcflib and vcflib's nested
dependencies. Those components retain their own license notices. The archive
is supplied for study and for the verifier's original downstream reference;
the submitted BWA must not vendor or depend on donor implementation code.
