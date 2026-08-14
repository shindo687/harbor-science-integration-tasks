"""Shared verifier-only SAM transformation and normalized VCF parsing."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def rewrite_sam_flags(source: Path, destination: Path, parameters: dict[str, Any]) -> None:
    rules = list(parameters.get("sam_flag_rules", []))
    with source.open(encoding="ascii") as input_handle, destination.open("w", encoding="ascii") as output_handle:
        for raw_line in input_handle:
            if raw_line.startswith("@") or not rules:
                output_handle.write(raw_line)
                continue
            fields = raw_line.rstrip("\n").split("\t")
            if len(fields) < 11:
                output_handle.write(raw_line)
                continue
            flag = int(fields[1])
            for rule in rules:
                if fields[0].startswith(str(rule["prefix"])):
                    flag |= int(rule["or_mask"])
            fields[1] = str(flag)
            output_handle.write("\t".join(fields) + "\n")


def parse_info(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    if text == ".":
        return result
    for item in text.split(";"):
        key, separator, value = item.partition("=")
        result[key] = value if separator else ""
    return result


def parse_calls(vcf: Path, sample: str) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []
    sample_column = -1
    with vcf.open(encoding="ascii") as handle:
        for raw_line in handle:
            if raw_line.startswith("##"):
                continue
            fields = raw_line.rstrip("\n").split("\t")
            if fields[0] == "#CHROM":
                if sample not in fields[9:]:
                    raise ValueError(f"VCF does not contain sample {sample!r}")
                sample_column = fields.index(sample)
                continue
            if raw_line.startswith("#") or not raw_line.strip():
                continue
            if sample_column < 0:
                raise ValueError("VCF has no #CHROM header")
            if len(fields) <= sample_column:
                raise ValueError("VCF record has too few columns")

            chrom, pos, _identifier, ref, alt, qual = fields[:6]
            alt_values = alt.split(",")
            if len(ref) != 1 or len(alt_values) != 1 or len(alt_values[0]) != 1:
                continue
            if ref not in "ACGT" or alt_values[0] not in "ACGT":
                continue
            info = parse_info(fields[7])
            format_keys = fields[8].split(":")
            sample_values = fields[sample_column].split(":")
            sample_data = dict(zip(format_keys, sample_values, strict=False))
            required = ("GT", "DP", "AD", "GL", "GQ")
            missing = [key for key in required if key not in sample_data]
            if missing or "DP" not in info:
                raise ValueError(f"VCF record is missing required values: {missing}")
            calls.append(
                {
                    "chrom": chrom,
                    "pos": int(pos),
                    "ref": ref,
                    "alt": alt_values[0],
                    "qual": float(qual),
                    "dp": int(info["DP"]),
                    "gt": sample_data["GT"],
                    "sample_dp": int(sample_data["DP"]),
                    "ad": [int(value) for value in sample_data["AD"].split(",")],
                    "gl": [float(value) for value in sample_data["GL"].split(",")],
                    "gq": float(sample_data["GQ"]),
                }
            )
    return calls
