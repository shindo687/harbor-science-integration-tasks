# AlgoBridge 0010: BWA absorbs bounded FreeBayes SNV calling

Authoring status: **accepted**. The formal Harbor Oracle passes all 15 hidden
differential cases and all five public examples with Reward `1.0`; the formal
NOP baseline receives Reward `0.0`. Both trials completed without exceptions.

The task asks an Agent to add a bounded native SNV caller to BWA. The reference
pipeline aligns reads with pristine BWA-MEM 0.7.17 and calls variants with real
FreeBayes 1.3.6. The candidate pipeline uses the submitted BWA for alignment
and its new `bwa snv-call` command for calling, without FreeBayes or its
libraries at runtime.

Locked inputs:

- BWA 0.7.17, commit `9f26bfcc7780753129b60717ecab0ebba6f04b7c`
- FreeBayes 1.3.6, commit `084dce52e54af5adbd1e2b0a67f3733dd8bfddc0`
  with all recursive submodules
- Ubuntu 22.04 image digest
  `sha256:3b06811b2afd352be909dd088a004166d665dc76d38b13eada33522a9d915c6f`
- Reference packages: BWA `0.7.17-6`, FreeBayes `1.3.6-1`, samtools `1.13-4`

BWA 0.7.17 predates GCC 10's `-fno-common` default. Both images append only
`-fcommon` to the upstream Makefile CFLAGS after extraction; the original
archive remains byte-exact and `source-lock.json` locks the resulting Makefile
SHA-256. This is a compiler-compatibility materialization step, not an
algorithm change.

The verifier runs references before physically removing FreeBayes, pristine
BWA, samtools and their source assets. It then rebuilds and runs the submitted
BWA as unprivileged UID 10001, with `/tests` unreadable. Source-policy and
legacy BWA-MEM parity checks are hard gates; 15 private real differential cases
determine the reward. See `source-lock.json` for exact trees, submodule commits,
archive hashes and runtime provenance.

Acceptance evidence is summarized in `validation/HARBOR_ACCEPTANCE.md`.
