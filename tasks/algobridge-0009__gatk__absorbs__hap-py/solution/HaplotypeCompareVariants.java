package org.broadinstitute.hellbender.tools.walkers.variantutils;

import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * A bounded, dependency-free haplotype-aware comparison primitive for biallelic
 * diploid SNPs and short indels.
 */
public final class HaplotypeCompareVariants {
    private static final int BLOCK_WINDOW = 30;
    private static final int MAX_VARIANTS_PER_SIDE = 32;
    private static final int MAX_HAPLOTYPE_CONFIGURATIONS = 4096;

    private HaplotypeCompareVariants() {
    }

    public static final class Variant {
        public final String id;
        public final int position;
        public final String ref;
        public final String alt;
        public final String genotype;

        public Variant(
                final String id,
                final int position,
                final String ref,
                final String alt,
                final String genotype) {
            this.id = id;
            this.position = position;
            this.ref = ref;
            this.alt = alt;
            this.genotype = genotype;
        }
    }

    public static final class AlleleStatus {
        public final String id;
        public final String status;

        private AlleleStatus(final String id, final String status) {
            this.id = id;
            this.status = status;
        }
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

        private Result(
                final List<AlleleStatus> truth,
                final List<AlleleStatus> query,
                final int truthTp,
                final int queryTp,
                final int fp,
                final int fn,
                final double precision,
                final double recall,
                final double f1) {
            this.truth = Collections.unmodifiableList(new ArrayList<>(truth));
            this.query = Collections.unmodifiableList(new ArrayList<>(query));
            this.truthTp = truthTp;
            this.queryTp = queryTp;
            this.fp = fp;
            this.fn = fn;
            this.precision = precision;
            this.recall = recall;
            this.f1 = f1;
        }
    }

    private static final class IndexedVariant {
        private final Variant variant;
        private final int originalIndex;
        private final boolean truth;

        private IndexedVariant(final Variant variant, final int originalIndex, final boolean truth) {
            this.variant = variant;
            this.originalIndex = originalIndex;
            this.truth = truth;
        }

        private int end() {
            return variant.position + variant.ref.length() - 1;
        }
    }

    /**
     * Compare truth and query calls over an uppercase reference slice.
     * Positions are one-based genomic coordinates anchored at referenceStart.
     */
    public static Result compare(
            final String reference,
            final int referenceStart,
            final List<Variant> truth,
            final List<Variant> query) {
        validateReference(reference, referenceStart);
        validateSide(reference, referenceStart, truth, "truth");
        validateSide(reference, referenceStart, query, "query");

        final List<IndexedVariant> all = new ArrayList<>();
        for (int i = 0; i < truth.size(); ++i) {
            all.add(new IndexedVariant(truth.get(i), i, true));
        }
        for (int i = 0; i < query.size(); ++i) {
            all.add(new IndexedVariant(query.get(i), i, false));
        }
        all.sort(Comparator
                .comparingInt((IndexedVariant iv) -> iv.variant.position)
                .thenComparingInt(IndexedVariant::end)
                .thenComparing(iv -> iv.truth ? 0 : 1)
                .thenComparing(iv -> iv.variant.id));

        final String[] truthStatus = new String[truth.size()];
        final String[] queryStatus = new String[query.size()];
        int cursor = 0;
        while (cursor < all.size()) {
            int end = cursor + 1;
            int blockEnd = all.get(cursor).end();
            while (end < all.size()
                    && all.get(end).variant.position <= blockEnd + BLOCK_WINDOW) {
                blockEnd = Math.max(blockEnd, all.get(end).end());
                ++end;
            }
            classifyBlock(reference, referenceStart, all.subList(cursor, end), truthStatus, queryStatus);
            cursor = end;
        }

        final List<AlleleStatus> truthResult = new ArrayList<>();
        final List<AlleleStatus> queryResult = new ArrayList<>();
        int truthTp = 0;
        int queryTp = 0;
        int fn = 0;
        int fp = 0;
        for (int i = 0; i < truth.size(); ++i) {
            final String status = truthStatus[i];
            truthResult.add(new AlleleStatus(truth.get(i).id, status));
            if ("TP".equals(status)) {
                ++truthTp;
            } else {
                ++fn;
            }
        }
        for (int i = 0; i < query.size(); ++i) {
            final String status = queryStatus[i];
            queryResult.add(new AlleleStatus(query.get(i).id, status));
            if ("TP".equals(status)) {
                ++queryTp;
            } else {
                ++fp;
            }
        }

        final double precision = queryTp + fp == 0 ? 1.0 : (double) queryTp / (queryTp + fp);
        final double recall = truthTp + fn == 0 ? 1.0 : (double) truthTp / (truthTp + fn);
        final double f1 = precision + recall == 0.0
                ? 0.0
                : 2.0 * precision * recall / (precision + recall);
        return new Result(truthResult, queryResult, truthTp, queryTp, fp, fn, precision, recall, f1);
    }

    private static void classifyBlock(
            final String reference,
            final int referenceStart,
            final List<IndexedVariant> block,
            final String[] truthStatus,
            final String[] queryStatus) {
        final List<IndexedVariant> truthBlock = new ArrayList<>();
        final List<IndexedVariant> queryBlock = new ArrayList<>();
        for (final IndexedVariant iv : block) {
            (iv.truth ? truthBlock : queryBlock).add(iv);
        }

        if (!truthBlock.isEmpty()
                && !queryBlock.isEmpty()
                && haplotypesMatch(reference, referenceStart, truthBlock, queryBlock)) {
            for (final IndexedVariant iv : truthBlock) {
                truthStatus[iv.originalIndex] = "TP";
            }
            for (final IndexedVariant iv : queryBlock) {
                queryStatus[iv.originalIndex] = "TP";
            }
            return;
        }

        final Map<String, IndexedVariant> unmatchedTruth = new LinkedHashMap<>();
        for (final IndexedVariant iv : truthBlock) {
            unmatchedTruth.put(simpleKey(iv.variant), iv);
        }
        for (final IndexedVariant iv : queryBlock) {
            final IndexedVariant matched = unmatchedTruth.remove(simpleKey(iv.variant));
            if (matched == null) {
                queryStatus[iv.originalIndex] = "FP";
            } else {
                truthStatus[matched.originalIndex] = "TP";
                queryStatus[iv.originalIndex] = "TP";
            }
        }
        for (final IndexedVariant iv : unmatchedTruth.values()) {
            truthStatus[iv.originalIndex] = "FN";
        }
    }

    private static boolean haplotypesMatch(
            final String reference,
            final int referenceStart,
            final List<IndexedVariant> truth,
            final List<IndexedVariant> query) {
        final Set<String> truthPairs = enumerateHaplotypePairs(reference, referenceStart, truth);
        final Set<String> queryPairs = enumerateHaplotypePairs(reference, referenceStart, query);
        for (final String pair : truthPairs) {
            if (queryPairs.contains(pair)) {
                return true;
            }
        }
        return false;
    }

    private static Set<String> enumerateHaplotypePairs(
            final String reference,
            final int referenceStart,
            final List<IndexedVariant> variants) {
        final List<IndexedVariant> sorted = new ArrayList<>(variants);
        sorted.sort(Comparator.comparingInt(iv -> iv.variant.position));
        int configurations = 1;
        for (final IndexedVariant iv : sorted) {
            if (isUnphasedHeterozygous(iv.variant.genotype)) {
                configurations *= 2;
                if (configurations > MAX_HAPLOTYPE_CONFIGURATIONS) {
                    throw new IllegalArgumentException("haplotype configuration limit exceeded");
                }
            }
        }

        final Set<String> result = new HashSet<>();
        enumerateAssignments(reference, referenceStart, sorted, 0, new int[sorted.size()], result);
        return result;
    }

    private static void enumerateAssignments(
            final String reference,
            final int referenceStart,
            final List<IndexedVariant> variants,
            final int index,
            final int[] assignments,
            final Set<String> result) {
        if (index == variants.size()) {
            final String hap0 = buildHaplotype(reference, referenceStart, variants, assignments, 1);
            final String hap1 = buildHaplotype(reference, referenceStart, variants, assignments, 2);
            if (hap0.compareTo(hap1) <= 0) {
                result.add(hap0 + '\u0000' + hap1);
            } else {
                result.add(hap1 + '\u0000' + hap0);
            }
            return;
        }

        final String genotype = variants.get(index).variant.genotype;
        if ("1/1".equals(genotype) || "1|1".equals(genotype)) {
            assignments[index] = 3;
            enumerateAssignments(reference, referenceStart, variants, index + 1, assignments, result);
        } else if ("1|0".equals(genotype)) {
            assignments[index] = 1;
            enumerateAssignments(reference, referenceStart, variants, index + 1, assignments, result);
        } else if ("0|1".equals(genotype)) {
            assignments[index] = 2;
            enumerateAssignments(reference, referenceStart, variants, index + 1, assignments, result);
        } else {
            assignments[index] = 1;
            enumerateAssignments(reference, referenceStart, variants, index + 1, assignments, result);
            assignments[index] = 2;
            enumerateAssignments(reference, referenceStart, variants, index + 1, assignments, result);
        }
    }

    private static String buildHaplotype(
            final String reference,
            final int referenceStart,
            final List<IndexedVariant> variants,
            final int[] assignments,
            final int haplotypeMask) {
        final StringBuilder haplotype = new StringBuilder(reference.length() + 64);
        int referenceOffset = 0;
        for (int i = 0; i < variants.size(); ++i) {
            if ((assignments[i] & haplotypeMask) == 0) {
                continue;
            }
            final Variant variant = variants.get(i).variant;
            final int start = variant.position - referenceStart;
            if (start < referenceOffset) {
                throw new IllegalArgumentException("overlapping alternate alleles on a haplotype");
            }
            haplotype.append(reference, referenceOffset, start);
            haplotype.append(variant.alt);
            referenceOffset = start + variant.ref.length();
        }
        haplotype.append(reference, referenceOffset, reference.length());
        return haplotype.toString();
    }

    private static String simpleKey(final Variant variant) {
        return variant.position + "\u0001" + variant.ref + "\u0001" + variant.alt
                + "\u0001" + genotypeClass(variant.genotype);
    }

    private static String genotypeClass(final String genotype) {
        return ("1/1".equals(genotype) || "1|1".equals(genotype)) ? "homalt" : "het";
    }

    private static boolean isUnphasedHeterozygous(final String genotype) {
        return "0/1".equals(genotype) || "1/0".equals(genotype);
    }

    private static void validateReference(final String reference, final int referenceStart) {
        if (reference == null || reference.length() < 64 || reference.length() > 512) {
            throw new IllegalArgumentException("reference length must be between 64 and 512");
        }
        if (referenceStart < 1) {
            throw new IllegalArgumentException("referenceStart must be positive");
        }
        if (!isDna(reference)) {
            throw new IllegalArgumentException("reference must contain only uppercase A/C/G/T");
        }
    }

    private static void validateSide(
            final String reference,
            final int referenceStart,
            final List<Variant> variants,
            final String label) {
        if (variants == null || variants.size() > MAX_VARIANTS_PER_SIDE) {
            throw new IllegalArgumentException(label + " must contain at most 32 variants");
        }
        final Set<String> ids = new HashSet<>();
        final List<Variant> sorted = new ArrayList<>();
        for (final Variant variant : variants) {
            if (variant == null
                    || variant.id == null
                    || variant.id.isEmpty()
                    || variant.ref == null
                    || variant.alt == null
                    || variant.genotype == null) {
                throw new IllegalArgumentException(label + " contains a null or incomplete variant");
            }
            if (!ids.add(variant.id)) {
                throw new IllegalArgumentException(label + " variant IDs must be unique");
            }
            if (variant.ref.isEmpty() || variant.alt.isEmpty()
                    || !isDna(variant.ref) || !isDna(variant.alt)) {
                throw new IllegalArgumentException("alleles must be non-empty uppercase A/C/G/T strings");
            }
            final boolean snp = variant.ref.length() == 1 && variant.alt.length() == 1;
            final boolean shortIndel = variant.ref.length() != variant.alt.length()
                    && Math.abs(variant.ref.length() - variant.alt.length()) <= 50;
            if (!snp && !shortIndel) {
                throw new IllegalArgumentException("only SNPs and indels up to 50 bp are supported");
            }
            if (!("0/1".equals(variant.genotype)
                    || "1/0".equals(variant.genotype)
                    || "0|1".equals(variant.genotype)
                    || "1|0".equals(variant.genotype)
                    || "1/1".equals(variant.genotype)
                    || "1|1".equals(variant.genotype))) {
                throw new IllegalArgumentException("unsupported diploid genotype");
            }
            final int start = variant.position - referenceStart;
            final int end = start + variant.ref.length();
            if (start < 0 || end > reference.length()) {
                throw new IllegalArgumentException("variant lies outside the reference slice");
            }
            if (!reference.regionMatches(start, variant.ref, 0, variant.ref.length())) {
                throw new IllegalArgumentException("REF allele does not match the reference slice");
            }
            sorted.add(variant);
        }

        sorted.sort(Comparator.comparingInt(v -> v.position));
        int previousEnd = Integer.MIN_VALUE;
        for (final Variant variant : sorted) {
            if (variant.position <= previousEnd) {
                throw new IllegalArgumentException(label + " variants may not overlap");
            }
            previousEnd = variant.position + variant.ref.length() - 1;
        }
    }

    private static boolean isDna(final String sequence) {
        for (int i = 0; i < sequence.length(); ++i) {
            final char base = sequence.charAt(i);
            if (base != 'A' && base != 'C' && base != 'G' && base != 'T') {
                return false;
            }
        }
        return true;
    }
}
