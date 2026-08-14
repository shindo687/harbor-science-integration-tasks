#!/usr/bin/env python3
"""Run the locked MAFFT -> pristine FastTree reference while assets exist."""

from __future__ import annotations

from pathlib import Path
import os
import subprocess
import tempfile

from common import format_fasta, normalize_mafft_names, parse_fasta, parse_newick


MAFFT = Path("/opt/reference-tools/mafft/bin/mafft")
MAFFT_BINARIES = Path("/opt/reference-tools/mafft/libexec/mafft")
FASTTREE = Path("/opt/reference-tools/FastTree")


def _run(command, *, timeout=30, env=None):
    completed = subprocess.run(
        [str(item) for item in command],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"reference command failed ({completed.returncode}): {' '.join(map(str, command))}\n"
            f"stderr:\n{completed.stderr[-4000:]}"
        )
    return completed


def run_reference(case):
    with tempfile.TemporaryDirectory(prefix="reference-case-") as directory:
        root = Path(directory)
        input_path = root / "input.fa"
        # Sorting makes the oracle and its tie behavior independent of the
        # presentation order used by permutation fixtures.
        input_path.write_text(format_fasta(sorted(case["records"])))
        command = [
            MAFFT,
            "--nuc" if case["alphabet"] == "dna" else "--amino",
            "--globalpair",
            "--maxiterate",
            "0",
            "--retree",
            "1",
            "--thread",
            "0",
            "--inputorder",
            "--op",
            "1.53",
            "--ep",
            "0.123",
            "--treeout",
            input_path,
        ]
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(root),
            "TMPDIR": str(root),
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
            "MAFFT_BINARIES": str(MAFFT_BINARIES),
        }
        aligned = _run(command, env=env).stdout
        alignment_path = root / "aligned.fa"
        alignment_path.write_text(aligned)
        guide_text = Path(str(input_path) + ".tree").read_text()
        tree_command = [FASTTREE]
        if case["alphabet"] == "dna":
            tree_command.append("-nt")
        tree_command.extend(["-quiet", "-noboot", alignment_path])
        final_tree = _run(tree_command, env=env).stdout.strip()
        return {
            "alignment_text": aligned,
            "alignment": parse_fasta(aligned),
            "guide_text": guide_text,
            "guide": normalize_mafft_names(parse_newick(guide_text)),
            "final_tree_text": final_tree,
            "final_tree": parse_newick(final_tree),
        }


def run_legacy(alignment_records):
    with tempfile.TemporaryDirectory(prefix="reference-legacy-") as directory:
        root = Path(directory)
        path = root / "aligned.fa"
        path.write_text(format_fasta(alignment_records))
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(root),
            "TMPDIR": str(root),
            "LC_ALL": "C.UTF-8",
            "LANG": "C.UTF-8",
        }
        result = _run([FASTTREE, "-nt", "-quiet", "-noboot", path], env=env)
        return result.stdout.strip(), parse_newick(result.stdout.strip())

