#!/usr/bin/env python3
"""Compile a candidate FastTree and verify all five published examples."""

from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile

from public_common import (
    alignment_homology,
    alignment_invariants,
    parse_fasta,
    parse_newick,
    tree_invariants,
    trees_equivalent,
)


def run(command, **kwargs):
    completed = subprocess.run(
        [str(value) for value in command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        **kwargs,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(map(str, command))}\n"
            f"{completed.stderr[-4000:]}"
        )
    return completed


def main(testbed):
    examples = Path(__file__).resolve().parent
    manifest = json.loads((examples / "manifest.json").read_text())
    sources = sorted(testbed.glob("*.c"))
    if not sources:
        raise RuntimeError("no root-level candidate C source found")
    with tempfile.TemporaryDirectory(prefix="fasttree-public-") as temporary:
        root = Path(temporary)
        binary = root / "FastTree"
        run(["gcc", "-O3", "-std=c99", "-I", testbed, "-o", binary, *sources, "-lm"])
        passed = 0
        for item in manifest["examples"]:
            directory = examples / item["directory"]
            case_root = root / item["id"]
            case_root.mkdir()
            aligned_path = case_root / "alignment.fa"
            guide_path = case_root / "guide.nwk"
            command = [binary]
            if item["alphabet"] == "dna":
                command.append("-nt")
            command.extend(
                [
                    "-quiet", "-noboot", "--align-small",
                    "--alignment-out", aligned_path,
                    "--guide-tree-out", guide_path,
                    "--align-matrix", item["matrix"],
                    "--align-gap-open", str(item["gap_open"]),
                    "--align-gap-extend", str(item["gap_extend"]),
                    directory / "input.fa",
                ]
            )
            result = run(command, cwd=case_root, timeout=30)
            inputs = parse_fasta((directory / "input.fa").read_text())
            expected_alignment = parse_fasta((directory / "expected_alignment.fa").read_text())
            candidate_alignment = parse_fasta(aligned_path.read_text())
            problems = alignment_invariants(inputs, candidate_alignment, item["alphabet"])
            if alignment_homology(expected_alignment) != alignment_homology(candidate_alignment):
                problems.append("alignment homology differs from published reference")
            names = [name for name, _ in inputs]
            expected_guide = parse_newick((directory / "expected_guide.nwk").read_text())
            candidate_guide = parse_newick(guide_path.read_text())
            problems += tree_invariants(candidate_guide, names, True)
            guide_ok, guide_detail = trees_equivalent(expected_guide, candidate_guide, 1e-5)
            if not guide_ok:
                problems.append(f"guide tree: {guide_detail}")
            expected_tree = parse_newick((directory / "expected_tree.nwk").read_text())
            candidate_tree = parse_newick(result.stdout.strip())
            problems += tree_invariants(candidate_tree, names, False)
            tree_ok, tree_detail = trees_equivalent(expected_tree, candidate_tree, 1e-5)
            if not tree_ok:
                problems.append(f"final tree: {tree_detail}")
            if problems:
                print(f"FAIL {item['id']}: {'; '.join(problems)}")
            else:
                print(f"PASS {item['id']}")
                passed += 1
        print(f"public examples: {passed}/{len(manifest['examples'])}")
        return 0 if passed == len(manifest["examples"]) else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")))

