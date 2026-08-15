# Add haplotype-aware variant comparison to GATK

Work in `/testbed`, a complete locked GATK 4.6.2.0 source tree. A complete
hap.py 0.3.15 source tree is available for documentation at
`/opt/donor-source`. Implement the bounded downstream capability natively in
GATK; the final solution must not invoke, import, bundle, or depend on hap.py.

Add exactly one UTF-8 Java source file and do not modify or remove existing
GATK files:

```text
src/main/java/org/broadinstitute/hellbender/tools/walkers/variantutils/HaplotypeCompareVariants.java
```

The source may import only `java.util` classes. It must not use file, network,
process, reflection, native, environment, system-property, or concurrency APIs.

## Required API

Declare a `public final class HaplotypeCompareVariants` in the native GATK
package above, with these public nested result/input types and entry point:

```java
public static final class Variant {
    public final String id;
    public final int position;
    public final String ref;
    public final String alt;
    public final String genotype;
    public Variant(String id, int position, String ref, String alt, String genotype);
}

public static final class AlleleStatus {
    public final String id;
    public final String status;
}

public static final class Result {
    public final List<AlleleStatus> truth;
    public final List<AlleleStatus> query;
    public final int truthTp;
    public final int queryTp;
    public final int fp;
    public final int fn;
    public final double precision;
    public final double recall;
    public final double f1;
}

public static Result compare(
    String reference,
    int referenceStart,
    List<Variant> truth,
    List<Variant> query);
```

## Bounded comparison contract

- `reference` is 64–512 uppercase `A/C/G/T` bases and `referenceStart` is its
  positive, one-based genomic start coordinate.
- Each side has at most 32 biallelic variants. IDs are nonempty and unique on
  that side. REF/ALT are nonempty uppercase DNA, REF exactly matches the
  supplied reference, and calls on one side may not overlap.
- Accept SNPs and insertions/deletions whose length change is at most 50 bases;
  reject MNPs, symbolic alleles, structural variants, and malformed calls.
- Genotypes are diploid alternate calls: `0/1`, `1/0`, `0|1`, `1|0`, `1/1`,
  or `1|1`.
- Form local superloci by joining calls separated by at most 30 reference
  bases. Enumerate the diploid haplotype pairs represented by phased and
  unphased calls, up to 4096 configurations per side. Haplotype chromosome
  labels are interchangeable, but relative phase is not.
- When any truth/query haplotype pair is exactly sequence-equivalent within a
  superlocus, classify every participating allele on both sides as `TP`. This
  covers shifted homopolymer indels and compound representations. Otherwise,
  match literal position/REF/ALT calls with the same heterozygous versus
  homozygous-alternate genotype class; unmatched truth calls are `FN` and
  unmatched query calls are `FP`.
- Preserve each side's input order in `Result.truth` and `Result.query`.
  `truthTp` and `queryTp` count the respective `TP` statuses. Precision is
  `queryTp/(queryTp+fp)`, recall is `truthTp/(truthTp+fn)`, and F1 is their
  harmonic mean. A zero precision or recall denominator yields `1.0`; a zero
  precision-plus-recall yields F1 `0.0`.

Raise an exception for every contract violation or haplotype-limit overflow.
Do not hard-code the disclosed cases.

## Validation

Five disclosed native hap.py comparisons are in `/examples`:

```bash
/opt/task-tools/run-public-examples
```

The separate, no-network verifier compiles only the added Java file with
OpenJDK 17 and runs it as an unprivileged user. A root-only oracle executes the
locked hap.py 0.3.15 `xcmp` engine with forced bounded haplotype comparison and
applies hap.py's `HapMatch` quantification semantics. It checks five public and
fifteen hidden cases, exact per-allele statuses and counts, metrics within
`1e-12`, twelve invalid inputs, two metamorphic identities, source integrity,
provenance, and candidate/reference isolation. Hidden reward is the fraction
of scientific cases passed; hard-gate failures earn zero.
