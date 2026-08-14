#!/usr/bin/env python3
"""Run the locked pristine BWA -> real FreeBayes reference pipeline.

This module deliberately invokes the real reference executables.  It does not
contain a stored answer table and it is never present during candidate
execution in the final verifier.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from task_io import parse_calls, rewrite_sam_flags


PRISTINE_BWA = Path("/opt/pristine-bwa-source/bwa")
FREEBAYES = Path("/usr/bin/freebayes")
SAMTOOLS = Path("/usr/bin/samtools")


def run(command: list[str], *, stdout: Any = subprocess.PIPE) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        command,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        message = completed.stderr.decode(errors="replace")
        raise RuntimeError(f"command failed ({completed.returncode}): {command!r}\n{message}")
    return completed


def reference_calls(case_dir: Path, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    reference = case_dir / "reference.fa"
    reads = case_dir / "reads.fastq"
    sample = str(parameters["sample"])
    ploidy = int(parameters["ploidy"])
    if ploidy not in (1, 2):
        raise ValueError("ploidy must be one or two")

    with tempfile.TemporaryDirectory(prefix="algobridge0010-reference-") as temporary:
        work = Path(temporary)
        work_reference = work / "reference.fa"
        shutil.copyfile(reference, work_reference)
        run([str(PRISTINE_BWA), "index", str(work_reference)])

        raw_sam = work / "raw.sam"
        transformed_sam = work / "alignments.sam"
        with raw_sam.open("wb") as sam_output:
            mem = subprocess.run(
                [
                    str(PRISTINE_BWA),
                    "mem",
                    "-R",
                    f"@RG\\tID:rg1\\tSM:{sample}",
                    str(work_reference),
                    str(reads),
                ],
                stdin=subprocess.DEVNULL,
                stdout=sam_output,
                stderr=subprocess.PIPE,
            )
        if mem.returncode != 0:
            raise RuntimeError(f"pristine bwa mem failed: {mem.stderr.decode(errors='replace')}")
        rewrite_sam_flags(raw_sam, transformed_sam, parameters)
        bam = work / "alignments.bam"
        run([str(SAMTOOLS), "sort", "-o", str(bam), str(transformed_sam)])
        run([str(SAMTOOLS), "index", str(bam)])

        vcf = work / "reference.vcf"
        command = [
            str(FREEBAYES),
            "--fasta-reference",
            str(work_reference),
            "--ploidy",
            str(ploidy),
            "--min-mapping-quality",
            str(int(parameters["min_mapping_quality"])),
            "--min-base-quality",
            str(int(parameters["min_base_quality"])),
            "--min-alternate-count",
            str(int(parameters["min_alternate_count"])),
            "--min-alternate-fraction",
            format(float(parameters["min_alternate_fraction"]), ".17g"),
            "--theta",
            format(float(parameters["theta"]), ".17g"),
            "--use-best-n-alleles",
            "2",
            "--haplotype-length",
            "0",
            "--throw-away-indel-obs",
            "--throw-away-mnps-obs",
            "--report-genotype-likelihood-max",
            "--genotype-qualities",
            str(bam),
        ]
        with vcf.open("wb") as output:
            run(command, stdout=output)
        return parse_calls(vcf, sample)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    parameters = json.loads((args.case_dir / "parameters.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": 1,
        "parameters": parameters,
        "calls": reference_calls(args.case_dir, parameters),
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
