#!/usr/bin/env python3
"""Disclosed and hidden bounded haplotype-comparison cases."""

from __future__ import annotations


def make_reference(seed=0, length=220, patches=()):
    alphabet = "ACGT"
    bases = [alphabet[(i * 3 + (i // 7) + seed) % 4] for i in range(length)]
    for position, sequence in patches:
        offset = position - 1
        bases[offset:offset + len(sequence)] = sequence
    return "".join(bases)


def variant(reference, identifier, position, alt, genotype="0/1", *, ref_length=1,
            reference_start=1):
    offset = position - reference_start
    return {
        "id": identifier,
        "position": position,
        "ref": reference[offset:offset + ref_length],
        "alt": alt,
        "genotype": genotype,
    }


def packet(name, reference, truth, query, reference_start=1):
    return {
        "name": name,
        "reference": reference,
        "reference_start": reference_start,
        "truth": truth,
        "query": query,
    }


def compound_deletion(name, seed, position, truth_gt="0/1", query_gt="0/1"):
    reference = make_reference(seed)
    offset = position - 1
    first, second, third = reference[offset:offset + 3]
    replacement = next(base for base in "ACGT" if base != first)
    truth = [
        variant(reference, "t_snp", position, replacement, truth_gt),
        variant(reference, "t_del", position + 1, second, truth_gt, ref_length=2),
    ]
    query = [variant(reference, "q_complex", position, replacement + second,
                     query_gt, ref_length=3)]
    return packet(name, reference, truth, query)


def compound_insertion(name, seed, position, truth_gt="0/1", query_gt="0/1"):
    reference = make_reference(seed)
    offset = position - 1
    first, second = reference[offset:offset + 2]
    replacement = next(base for base in "TGCA" if base != first)
    inserted = next(base for base in "GACT" if base != second)
    truth = [
        variant(reference, "t_snp", position, replacement, truth_gt),
        variant(reference, "t_ins", position + 1, second + inserted, truth_gt),
    ]
    query = [variant(reference, "q_complex", position,
                     replacement + second + inserted, query_gt, ref_length=2)]
    return packet(name, reference, truth, query)


def public_cases():
    exact_ref = make_reference(1)
    deletion_ref = make_reference(2, patches=((38, "AAAAAAAAAA"),))
    mixed_ref = make_reference(3, length=240, patches=((70, "CCCCCCCCCC"),))
    phased_ref = make_reference(0, patches=((96, "GGGGGGGGGG"),))
    return [
        packet("public_exact_snp", exact_ref,
               [variant(exact_ref, "truth_snp", 27, "A" if exact_ref[26] != "A" else "C")],
               [variant(exact_ref, "query_snp", 27, "A" if exact_ref[26] != "A" else "C")]),
        packet("public_shifted_homopolymer_deletion", deletion_ref,
               [variant(deletion_ref, "truth_del", 40, "A", "1/1", ref_length=2)],
               [variant(deletion_ref, "query_del", 44, "A", "1/1", ref_length=2)]),
        compound_deletion("public_compound_snp_deletion", 3, 55),
        packet("public_mixed_tp_fp_fn", mixed_ref,
               [variant(mixed_ref, "truth_exact", 20, "T" if mixed_ref[19] != "T" else "A"),
                variant(mixed_ref, "truth_shift", 72, "C", ref_length=2),
                variant(mixed_ref, "truth_only", 150, "G" if mixed_ref[149] != "G" else "A")],
               [variant(mixed_ref, "query_exact", 20, "T" if mixed_ref[19] != "T" else "A"),
                variant(mixed_ref, "query_shift", 76, "C", ref_length=2),
                variant(mixed_ref, "query_only", 210, "C" if mixed_ref[209] != "C" else "A")]),
        packet("public_phased_truth_unphased_query", phased_ref,
               [variant(phased_ref, "truth_snp", 72, "A" if phased_ref[71] != "A" else "C", "1|0"),
                variant(phased_ref, "truth_ins", 98, "GG", "1|0")],
               [variant(phased_ref, "query_snp", 72, "A" if phased_ref[71] != "A" else "C", "0/1"),
                variant(phased_ref, "query_ins", 101, "GG", "1/0")]),
    ]


def hidden_cases():
    exact_indel_ref = make_reference(1)
    insertion_ref = make_reference(2, patches=((42, "TTTTTTTTTT"),))
    mismatch_ref = make_reference(3)
    missing_ref = make_reference(0)
    pair_ref = make_reference(1)
    hom_ref = make_reference(2, patches=((62, "AAAAAAAAAAAA"),))
    offset_ref = make_reference(3, length=180)
    long_ref = make_reference(0, length=260)
    configs_ref = make_reference(1, length=260)
    block_ref = make_reference(2, length=280, patches=((112, "GGGGGGGGGG"),))
    near_ref = make_reference(3, patches=((82, "CCCCCCCCCC"),))

    long_del_alt = long_ref[29]
    long_ins_ref = long_ref[179]
    truth_configs = []
    query_configs = []
    for index, position in enumerate(range(20, 120, 10)):
        ref = configs_ref[position - 1]
        alt = next(base for base in "ACGT" if base != ref)
        truth_configs.append(variant(configs_ref, f"t_cfg_{index}", position, alt, "0/1"))
        query_configs.append(variant(configs_ref, f"q_cfg_{index}", position, alt, "1/0"))

    return [
        packet("hidden_exact_short_deletion", exact_indel_ref,
               [variant(exact_indel_ref, "truth_del", 33, exact_indel_ref[32], ref_length=3)],
               [variant(exact_indel_ref, "query_del", 33, exact_indel_ref[32], ref_length=3)]),
        packet("hidden_shifted_homopolymer_insertion", insertion_ref,
               [variant(insertion_ref, "truth_ins", 44, "TT")],
               [variant(insertion_ref, "query_ins", 48, "TT")]),
        compound_insertion("hidden_compound_snp_insertion", 2, 66),
        packet("hidden_genotype_mismatch", mismatch_ref,
               [variant(mismatch_ref, "truth_hom", 41, "A" if mismatch_ref[40] != "A" else "C", "1/1")],
               [variant(mismatch_ref, "query_het", 41, "A" if mismatch_ref[40] != "A" else "C", "0/1")]),
        packet("hidden_truth_only", missing_ref,
               [variant(missing_ref, "truth_only", 75, "G" if missing_ref[74] != "G" else "T")], []),
        packet("hidden_query_only", missing_ref, [],
               [variant(missing_ref, "query_only", 85, "C" if missing_ref[84] != "C" else "A")]),
        packet("hidden_two_exact_calls", pair_ref,
               [variant(pair_ref, "truth_a", 25, "T" if pair_ref[24] != "T" else "A", "1|0"),
                variant(pair_ref, "truth_b", 45, "G" if pair_ref[44] != "G" else "C", "0|1")],
               [variant(pair_ref, "query_a", 25, "T" if pair_ref[24] != "T" else "A", "0|1"),
                variant(pair_ref, "query_b", 45, "G" if pair_ref[44] != "G" else "C", "1|0")]),
        packet("hidden_homalt_shifted_deletion", hom_ref,
               [variant(hom_ref, "truth_del", 64, "A", "1|1", ref_length=2)],
               [variant(hom_ref, "query_del", 69, "A", "1/1", ref_length=2)]),
        packet("hidden_nonunit_reference_start", offset_ref,
               [variant(offset_ref, "truth_offset", 1040,
                        "A" if offset_ref[39] != "A" else "C", reference_start=1001)],
               [variant(offset_ref, "query_offset", 1040,
                        "A" if offset_ref[39] != "A" else "C", reference_start=1001)],
               reference_start=1001),
        packet("hidden_maximum_deletion_length", long_ref,
               [variant(long_ref, "truth_del50", 30, long_del_alt, "1/1", ref_length=51)],
               [variant(long_ref, "query_del50", 30, long_del_alt, "1|1", ref_length=51)]),
        packet("hidden_maximum_insertion_length", long_ref,
               [variant(long_ref, "truth_ins50", 180, long_ins_ref + "ACGT" * 12 + "AC", "0/1")],
               [variant(long_ref, "query_ins50", 180, long_ins_ref + "ACGT" * 12 + "AC", "1/0")]),
        packet("hidden_ten_unphased_calls", configs_ref, truth_configs, query_configs),
        packet("hidden_independent_blocks", block_ref,
               [variant(block_ref, "truth_left", 18, "A" if block_ref[17] != "A" else "C"),
                variant(block_ref, "truth_shift", 114, "G", ref_length=2),
                variant(block_ref, "truth_right_only", 230, "T" if block_ref[229] != "T" else "A")],
               [variant(block_ref, "query_left", 18, "A" if block_ref[17] != "A" else "C"),
                variant(block_ref, "query_shift", 119, "G", ref_length=2),
                variant(block_ref, "query_right_only", 270, "C" if block_ref[269] != "C" else "A")]),
        packet("hidden_near_haplotype_mismatch", near_ref,
               [variant(near_ref, "truth_del", 84, "C", ref_length=2)],
               [variant(near_ref, "query_del", 88, "CT", ref_length=3)]),
        packet("hidden_empty_comparison", make_reference(0), [], []),
    ]
