# ALGOBRIDGE-0009 — GATK absorbs hap.py

This Harbor task asks an agent to add one native GATK Java primitive for
bounded diploid haplotype-aware truth/query VCF comparison. The separate
verifier uses a root-only build of official hap.py `v0.3.15` as the scientific
oracle and evaluates the candidate without network access.

See `instruction.md` for the participant contract and `source-lock.json` for
exact source and runtime provenance.
