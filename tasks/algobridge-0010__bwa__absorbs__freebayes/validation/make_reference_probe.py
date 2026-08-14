#!/usr/bin/env python3
"""Create a deterministic one-locus read set for real-reference exploration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("--ref-count", type=int, default=10)
    parser.add_argument("--alt-count", type=int, default=10)
    parser.add_argument("--quality", type=int, default=40)
    parser.add_argument("--ploidy", type=int, choices=(1, 2), default=2)
    parser.add_argument("--balanced-strands", action="store_true")
    parser.add_argument("--stagger", type=int, default=0)
    args = parser.parse_args()

    rng = random.Random(10010)
    reference = "".join(rng.choice("ACGT") for _ in range(1000))
    locus = 500
    ref = reference[locus]
    alt = next(base for base in "ACGT" if base != ref)
    if args.stagger < 0 or args.stagger > 20:
        parser.error("--stagger must be between zero and 20")

    def reverse_complement(sequence: str) -> str:
        return sequence.translate(str.maketrans("ACGT", "TGCA"))[::-1]

    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "reference.fa").open("w", encoding="ascii") as handle:
        handle.write(">chr1\n")
        for offset in range(0, len(reference), 80):
            handle.write(reference[offset : offset + 80] + "\n")

    with (args.output / "reads.fastq").open("w", encoding="ascii") as handle:
        for allele, count in ((ref, args.ref_count), (alt, args.alt_count)):
            for index in range(count):
                shift = index % (2 * args.stagger + 1) - args.stagger
                start = locus - 50 + shift
                template = reference[start : start + 100]
                query_position = locus - start
                sequence = template[:query_position] + allele + template[query_position + 1 :]
                quality = chr(args.quality + 33) * len(sequence)
                if args.balanced_strands and index % 2 == 1:
                    sequence = reverse_complement(sequence)
                    quality = quality[::-1]
                handle.write(f"@{allele}_{index}\n{sequence}\n+\n{quality}\n")

    (args.output / "expected-locus.tsv").write_text(
        f"chr1\t{locus + 1}\t{ref}\t{alt}\n", encoding="ascii"
    )
    (args.output / "parameters.json").write_text(
        json.dumps(
            {
                "sample": "SAMPLE",
                "ploidy": args.ploidy,
                "min_base_quality": 0,
                "min_mapping_quality": 0,
                "min_alternate_count": 1,
                "min_alternate_fraction": 0.0,
                "theta": 0.001,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()
