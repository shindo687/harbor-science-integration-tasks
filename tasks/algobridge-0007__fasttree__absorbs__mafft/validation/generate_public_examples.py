#!/usr/bin/env python3
"""Regenerate public examples from the locked reference tools in the verifier image."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, "/tests")

from common import format_fasta  # noqa: E402
from guide_oracle import bounded_upgma  # noqa: E402
from reference_runner import run_reference  # noqa: E402


PUBLIC_CASES = [
    {
        "id": "public_dna_pair_indel",
        "alphabet": "dna",
        "records": [
            ("pub_dna_b", "CGTACCAAGGTTAC"),
            ("pub_dna_a", "CGTACCAATTTGGTTAC"),
        ],
    },
    {
        "id": "public_dna_terminal",
        "alphabet": "dna",
        "records": [
            ("terminal_c", "GGCATGACCTTAGA"),
            ("terminal_a", "CATGACCTTAGA"),
            ("terminal_b", "GGCATGACCTCAGA"),
        ],
    },
    {
        "id": "public_dna_duplicates",
        "alphabet": "dna",
        "records": [
            ("duplicate_d", "AACGTTACCTGA"),
            ("duplicate_b", "AACGTTACCTGA"),
            ("duplicate_c", "AACGTTGGGACCTGA"),
            ("duplicate_a", "AACGTTACCTAA"),
        ],
    },
    {
        "id": "public_protein_motif",
        "alphabet": "protein",
        "records": [
            ("motif_c", "MTRKQLGGGVIDEAL"),
            ("motif_a", "MTRKQLVIDEAL"),
            ("motif_d", "MTRKQLGGGVIDDAL"),
            ("motif_b", "MTRKQLVIDDAL"),
        ],
    },
    {
        "id": "public_protein_six",
        "alphabet": "protein",
        "records": [
            ("six_f", "MALWQKLLPLVSSAFR"),
            ("six_c", "MALWQKGGGLLPLVSSAYR"),
            ("six_a", "MALWQKLLPLVSSAYR"),
            ("six_e", "MALWQKLLPLVSTAFR"),
            ("six_b", "MALWQKLLPLVSTAYR"),
            ("six_d", "MALWQKGGGLLPLVSTAYR"),
        ],
    },
]


def serialize_newick(node, parent_height=None):
    if node.children:
        body = "(" + ",".join(serialize_newick(child, 0.0) for child in node.children) + ")"
    else:
        body = node.name
    if parent_height is not None:
        body += f":{float(node.length or 0.0):.10f}"
    return body


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(output_root):
    output_root.mkdir(parents=True, exist_ok=True)
    entries = []
    for index, case in enumerate(PUBLIC_CASES, 1):
        directory = output_root / f"{index:02d}_{case['id']}"
        directory.mkdir(parents=True, exist_ok=True)
        reference = run_reference(case)
        guide = bounded_upgma(case["records"], case["alphabet"], 4.0, 0.75)
        files = {
            "input": directory / "input.fa",
            "alignment": directory / "expected_alignment.fa",
            "guide_tree": directory / "expected_guide.nwk",
            "final_tree": directory / "expected_tree.nwk",
        }
        files["input"].write_text(format_fasta(case["records"]))
        files["alignment"].write_text(reference["alignment_text"])
        files["guide_tree"].write_text(serialize_newick(guide) + ";\n")
        files["final_tree"].write_text(reference["final_tree_text"] + "\n")
        entries.append(
            {
                "id": case["id"],
                "alphabet": case["alphabet"],
                "directory": directory.name,
                "gap_open": 4.0,
                "gap_extend": 0.75,
                "matrix": "identity" if case["alphabet"] == "dna" else "blosum62",
                "sha256": {name: digest(path) for name, path in files.items()},
            }
        )
    manifest = {
        "schema_version": 1,
        "generator": "locked MAFFT core -> locked FastTree plus independent bounded UPGMA",
        "examples": entries,
    }
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    )


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("public-examples")
    main(target)

