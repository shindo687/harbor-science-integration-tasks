# Direct verifier evidence

Status: pre-Harbor acceptance evidence generated on 2026-08-14.

The clean-room Oracle was materialized into the locked BWA source and tested
inside the verifier image. The verifier generated every fixture at runtime,
ran pristine BWA-MEM 0.7.17, samtools 1.13 and real FreeBayes 1.3.6, removed
the reference executables/sources, rebuilt the candidate as UID 10001, and
then ran the submitted BWA-MEM plus native `snv-call` pipeline.

Results:

- source-policy hard gate: pass;
- exact donor 72-token windows: 0;
- normalized donor 128-token windows: 0;
- candidate isolation: pass;
- candidate build as UID 10001: pass;
- legacy BWA-MEM parity: pass;
- real reference determinism: pass;
- public examples: 5/5;
- hidden differential cases: 15/15;
- direct reward: 1.0;
- NOP baseline: reward 0 at the source-policy gate.

The direct Oracle run used verifier image
`sha256:f812f6cf81219f6ad5c3d7a90e6c161de9ed045a836262822bccea118a2af0ae`
before the final donor-library deletion hardening. A fresh image and formal
Harbor Oracle/NOP trials are required before changing the Task status to
accepted.
