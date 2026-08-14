#!/usr/bin/env python3
"""Generate deterministic bounded SNV fixtures from verifier-only specs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
from typing import Any


DNA_COMPLEMENT = str.maketrans("ACGT", "TGCA")


def reverse_complement(sequence: str) -> str:
    return sequence.translate(DNA_COMPLEMENT)[::-1]


def alternate_base(reference: str, offset: int = 0) -> str:
    choices = [base for base in "ACGT" if base != reference]
    return choices[offset % len(choices)]


def make_fixture(spec: dict[str, Any], output: Path) -> None:
    rng = random.Random(int(spec["seed"]))
    length = int(spec.get("reference_length", 3200))
    read_length = int(spec.get("read_length", 100))
    reference = "".join(rng.choice("ACGT") for _ in range(length))
    output.mkdir(parents=True, exist_ok=True)

    contigs = [(str(spec.get("contig", "chr1")), reference)]
    if spec.get("duplicate_contig", False):
        contigs.append((str(spec.get("duplicate_contig_name", "chr2")), reference))
    with (output / "reference.fa").open("w", encoding="ascii") as handle:
        for name, sequence in contigs:
            handle.write(f">{name}\n")
            for start in range(0, len(sequence), 80):
                handle.write(sequence[start : start + 80] + "\n")

    expected: list[dict[str, Any]] = []
    with (output / "reads.fastq").open("w", encoding="ascii") as handle:
        for locus_index, locus_spec in enumerate(spec["loci"]):
            position = int(locus_spec["position"])
            if position < read_length or position + read_length >= length:
                raise ValueError(f"locus {position} is too close to a contig edge")
            ref = reference[position]
            alt = str(locus_spec.get("alt", alternate_base(ref, locus_index)))
            if alt not in "ACGT" or alt == ref:
                raise ValueError(f"invalid alternate allele {alt!r}")
            expected.append({"chrom": contigs[0][0], "pos": position + 1, "ref": ref, "alt": alt})

            ref_count = int(locus_spec.get("ref_count", 0))
            alt_count = int(locus_spec.get("alt_count", 0))
            duplicate_alt_count = int(locus_spec.get("duplicate_alt_count", 0))
            default_quality = int(locus_spec.get("quality", 30))
            ref_quality = int(locus_spec.get("ref_quality", default_quality))
            alt_quality = int(locus_spec.get("alt_quality", default_quality))
            balanced = bool(locus_spec.get("balanced_strands", True))
            stagger = int(locus_spec.get("stagger", 3))
            if stagger < 0 or stagger > 20:
                raise ValueError("stagger must be between zero and 20")

            for allele_name, allele, count, quality in (
                ("ref", ref, ref_count, ref_quality),
                ("alt", alt, alt_count, alt_quality),
            ):
                for read_index in range(count):
                    shift = read_index % (2 * stagger + 1) - stagger
                    start = position - read_length // 2 + shift
                    template = reference[start : start + read_length]
                    query_position = position - start
                    sequence = template[:query_position] + allele + template[query_position + 1 :]
                    qualities = chr(quality + 33) * read_length
                    reverse = balanced and read_index % 2 == 1
                    if reverse:
                        sequence = reverse_complement(sequence)
                        qualities = qualities[::-1]
                    duplicate = allele_name == "alt" and read_index >= count - duplicate_alt_count
                    prefix = "DUP_" if duplicate else "READ_"
                    name = f"{prefix}{locus_index}_{allele_name}_{read_index}"
                    handle.write(f"@{name}\n{sequence}\n+\n{qualities}\n")

    parameters = {
        "sample": str(spec.get("sample", "SAMPLE")),
        "ploidy": int(spec.get("ploidy", 2)),
        "min_base_quality": int(spec.get("min_base_quality", 0)),
        "min_mapping_quality": int(spec.get("min_mapping_quality", 0)),
        "min_alternate_count": int(spec.get("min_alternate_count", 1)),
        "min_alternate_fraction": float(spec.get("min_alternate_fraction", 0.0)),
        "theta": float(spec.get("theta", 0.001)),
        "sam_flag_rules": [{"prefix": "DUP_", "or_mask": 0x400}],
    }
    (output / "parameters.json").write_text(
        json.dumps(parameters, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )
    (output / "expected-loci.json").write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n", encoding="ascii"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    make_fixture(json.loads(args.spec.read_text(encoding="utf-8")), args.output)


if __name__ == "__main__":
    main()
