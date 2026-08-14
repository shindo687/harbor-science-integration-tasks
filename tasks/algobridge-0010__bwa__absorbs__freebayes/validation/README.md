# Validation status

Source provenance is locked. Differential fixtures, isolation gates, direct
controls and formal Harbor Oracle/NOP evidence are still pending.

## Source-lock smoke checks

The following development checks pass on the locked inputs:

- Agent image builds pristine BWA with the documented `-fcommon` materialization.
- Agent image contains FreeBayes source for study but no FreeBayes executable.
- Verifier image reports BWA `0.7.17-r1188`, FreeBayes `v1.3.6` and samtools `1.13`.

## Real-reference probe

`make_reference_probe.py` creates a deterministic one-locus FASTQ/FASTA pair
for exercising the locked reference image.  It is an authoring aid, not a
grader fixture and not a stored reference oracle.

The probe established the bounded likelihood contract directly from real
FreeBayes output.  For a genotype that contains an observed allele, the
experimental FreeBayes likelihood adds the log allele-sampling probability.
For an allele outside the genotype it adds the joint base/mapping error
probability, scaled by the default `0.9` read-dependence factor.  VCF `GL`
values are those log likelihoods converted to log10 and normalized to a
maximum of zero.  Site `QUAL` and sample `GQ` additionally use FreeBayes'
single-population posterior priors; those values must therefore be validated
against the executable rather than inferred from `GL` alone.
- Both source archives match the SHA-256 and entry counts in `source-lock.json`.
- Both image copies of `source-lock.json` are byte-identical to the root lock.

These are source/runtime provenance checks only, not task acceptance evidence.
