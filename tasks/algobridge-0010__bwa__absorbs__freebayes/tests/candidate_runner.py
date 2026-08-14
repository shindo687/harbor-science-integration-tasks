#!/usr/bin/env python3
"""Run the submitted BWA-MEM -> submitted native snv-call pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any

from task_io import parse_calls, rewrite_sam_flags


def checked_run(command: list[str], *, stdout: Any = subprocess.PIPE) -> subprocess.CompletedProcess[bytes]:
    completed = subprocess.run(
        command,
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=stdout,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"candidate command failed ({completed.returncode}): {command!r}\n"
            + completed.stderr.decode(errors="replace")
        )
    return completed


def candidate_calls(binary: Path, case_dir: Path, parameters: dict[str, Any]) -> list[dict[str, Any]]:
    sample = str(parameters["sample"])
    with tempfile.TemporaryDirectory(prefix="algobridge0010-candidate-") as temporary:
        work = Path(temporary)
        reference = work / "reference.fa"
        shutil.copyfile(case_dir / "reference.fa", reference)
        checked_run([str(binary), "index", str(reference)])

        raw_sam = work / "raw.sam"
        with raw_sam.open("wb") as output:
            checked_run(
                [
                    str(binary),
                    "mem",
                    "-R",
                    f"@RG\\tID:rg1\\tSM:{sample}",
                    str(reference),
                    str(case_dir / "reads.fastq"),
                ],
                stdout=output,
            )
        transformed_sam = work / "alignments.sam"
        rewrite_sam_flags(raw_sam, transformed_sam, parameters)

        vcf = work / "candidate.vcf"
        command = [
            str(binary),
            "snv-call",
            "-f",
            str(reference),
            "-s",
            sample,
            "-p",
            str(int(parameters["ploidy"])),
            "--min-base-quality",
            str(int(parameters["min_base_quality"])),
            "--min-mapping-quality",
            str(int(parameters["min_mapping_quality"])),
            "--min-alternate-count",
            str(int(parameters["min_alternate_count"])),
            "--min-alternate-fraction",
            format(float(parameters["min_alternate_fraction"]), ".17g"),
            "--theta",
            format(float(parameters["theta"]), ".17g"),
            str(transformed_sam),
        ]
        with vcf.open("wb") as output:
            checked_run(command, stdout=output)
        return parse_calls(vcf, sample)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("case_dir", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    parameters = json.loads((args.case_dir / "parameters.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": 1,
        "parameters": parameters,
        "calls": candidate_calls(args.binary, args.case_dir, parameters),
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
