#!/usr/bin/env python3
"""Root-only adapter around the locked hap.py v0.3.15 xcmp binaries."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile


REFERENCE_BIN = Path(os.environ.get("HAPPY_REFERENCE_BIN", "/opt/reference-happy/bin"))
XCMP = REFERENCE_BIN / "xcmp"
BGZIP = REFERENCE_BIN / "bgzip"
TABIX = REFERENCE_BIN / "tabix"


def write_fasta(directory, packet):
    prefix = "A" * (packet["reference_start"] - 1)
    sequence = prefix + packet["reference"] + "A" * 40
    fasta = directory / "reference.fa"
    fasta.write_text(">chr1\n" + sequence + "\n", encoding="ascii")
    (directory / "reference.fa.fai").write_text(
        f"chr1\t{len(sequence)}\t6\t{len(sequence)}\t{len(sequence) + 1}\n",
        encoding="ascii",
    )
    return fasta, len(sequence)


def write_vcf(directory, name, variants, contig_length):
    raw = directory / f"{name}.vcf"
    lines = [
        "##fileformat=VCFv4.2",
        f"##contig=<ID=chr1,length={contig_length}>",
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tSAMPLE",
    ]
    for item in sorted(variants, key=lambda value: value["position"]):
        lines.append("\t".join((
            "chr1", str(item["position"]), item["id"], item["ref"], item["alt"],
            "60", "PASS", ".", "GT", item["genotype"],
        )))
    raw.write_text("\n".join(lines) + "\n", encoding="ascii")
    compressed = directory / f"{name}.vcf.gz"
    with compressed.open("wb") as output:
        completed = subprocess.run(
            [str(BGZIP), "-c", str(raw)], stdout=output, stderr=subprocess.PIPE,
            timeout=20, check=False,
        )
    if completed.returncode:
        raise RuntimeError(f"bgzip failed: {completed.stderr.decode(errors='replace')[-1000:]}")
    completed = subprocess.run(
        [str(TABIX), "-f", "-p", "vcf", str(compressed)],
        text=True, capture_output=True, timeout=20, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"tabix failed: {completed.stderr[-1000:]}")
    return compressed


def parse_info(value):
    result = {}
    for field in value.split(";"):
        if "=" in field:
            key, content = field.split("=", 1)
            result[key] = content
        elif field and field != ".":
            result[field] = True
    return result


def quantify(packet, output_vcf):
    truth_lookup = {
        (item["position"], item["ref"], item["alt"]): index
        for index, item in enumerate(packet["truth"])
    }
    query_lookup = {
        (item["position"], item["ref"], item["alt"]): index
        for index, item in enumerate(packet["query"])
    }
    truth_status = [None] * len(packet["truth"])
    query_status = [None] * len(packet["query"])

    for line in output_vcf.read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        fields = line.split("\t")
        if len(fields) < 11:
            raise RuntimeError("xcmp emitted a malformed VCF record")
        key = (int(fields[1]), fields[3], fields[4])
        info = parse_info(fields[7])
        if "IMPORT_FAIL" in info:
            raise RuntimeError("xcmp could not import a bounded test variant")
        quantified = "TP" if "HapMatch" in info or info.get("type") == "TP" else None
        truth_gt = fields[9].split(":", 1)[0]
        query_gt = fields[10].split(":", 1)[0]
        if truth_gt not in {".", "./.", ".|."}:
            if key not in truth_lookup:
                raise RuntimeError(f"cannot map xcmp truth record {key}")
            truth_status[truth_lookup[key]] = quantified or "FN"
        if query_gt not in {".", "./.", ".|."}:
            if key not in query_lookup:
                raise RuntimeError(f"cannot map xcmp query record {key}")
            query_status[query_lookup[key]] = quantified or "FP"

    if any(value is None for value in truth_status + query_status):
        raise RuntimeError("xcmp did not emit every bounded input variant")
    truth_tp = truth_status.count("TP")
    query_tp = query_status.count("TP")
    fn = truth_status.count("FN")
    fp = query_status.count("FP")
    precision = 1.0 if query_tp + fp == 0 else query_tp / (query_tp + fp)
    recall = 1.0 if truth_tp + fn == 0 else truth_tp / (truth_tp + fn)
    f1 = 0.0 if precision + recall == 0.0 else 2.0 * precision * recall / (precision + recall)
    if not all(math.isfinite(value) for value in (precision, recall, f1)):
        raise RuntimeError("non-finite summary metric")
    return {
        "truth": [{"id": item["id"], "status": truth_status[index]}
                  for index, item in enumerate(packet["truth"])],
        "query": [{"id": item["id"], "status": query_status[index]}
                  for index, item in enumerate(packet["query"])],
        "summary": {
            "truth_tp": truth_tp,
            "query_tp": query_tp,
            "fp": fp,
            "fn": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        },
    }


def compare(packet):
    with tempfile.TemporaryDirectory(prefix="hap-py-reference-") as temp_name:
        directory = Path(temp_name)
        fasta, contig_length = write_fasta(directory, packet)
        truth = write_vcf(directory, "truth", packet["truth"], contig_length)
        query = write_vcf(directory, "query", packet["query"], contig_length)
        output = directory / "xcmp.vcf"
        errors = directory / "xcmp-errors.txt"
        completed = subprocess.run(
            [str(XCMP), "--input-vcfs", str(truth), str(query),
             "--reference", str(fasta), "--output-vcf", str(output),
             "--output-errors", str(errors), "--window", "30",
             "--expand-hapblocks", "30", "--max-n-haplotypes", "4096",
             "--always-hapcmp", "true", "--progress", "false"],
            text=True, capture_output=True, timeout=30, check=False,
        )
        if completed.returncode:
            detail = completed.stderr[-1500:] + completed.stdout[-500:]
            if errors.exists():
                detail += errors.read_text(encoding="utf-8", errors="replace")[-1000:]
            raise RuntimeError(f"xcmp failed ({completed.returncode}): {detail}")
        return quantify(packet, output)


def main():
    for line in sys.stdin:
        try:
            packet = json.loads(line)
            result = compare(packet)
            print(json.dumps({"ok": True, "result": result}, separators=(",", ":")), flush=True)
        except Exception as error:
            print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}), flush=True)


if __name__ == "__main__":
    main()
