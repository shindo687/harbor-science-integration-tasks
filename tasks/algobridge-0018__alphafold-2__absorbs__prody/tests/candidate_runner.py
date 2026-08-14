#!/usr/bin/env python3
"""Immutable JSON protocol runner for the submitted AlphaFold API."""

from __future__ import annotations

import json
import sys

import numpy as np
from alphafold.common import protein as af_protein
from alphafold.common.normal_modes import analyze_normal_modes


REQUIRED = (
    "model", "residue_mapping", "network_matrix", "zero_mode_count",
    "eigenvalues", "modes", "msf", "cross_correlation",
)


def parse_structure(case):
    if case["format"] == "pdb":
        return af_protein.from_pdb_string(case["structure"])
    if case["format"] == "mmcif":
        return af_protein.from_mmcif_string(case["structure"])
    raise ValueError("unsupported structure format")


def encode_mapping(mapping):
    return [
        {
            "source_index": int(item["source_index"]),
            "chain_index": int(item["chain_index"]),
            "residue_index": int(item["residue_index"]),
            "aatype": int(item["aatype"]),
        }
        for item in mapping
    ]


def encode(result):
    return {
        "model": str(result["model"]),
        "residue_mapping": encode_mapping(result["residue_mapping"]),
        "network_matrix": np.asarray(result["network_matrix"], dtype=float).tolist(),
        "zero_mode_count": int(result["zero_mode_count"]),
        "eigenvalues": np.asarray(result["eigenvalues"], dtype=float).tolist(),
        "modes": np.asarray(result["modes"], dtype=float).tolist(),
        "msf": np.asarray(result["msf"], dtype=float).tolist(),
        "cross_correlation": np.asarray(
            result["cross_correlation"], dtype=float
        ).tolist(),
    }


def run_one(case):
    try:
        structure = parse_structure(case)
        result = analyze_normal_modes(structure, **case["arguments"])
        if not isinstance(result, dict):
            raise TypeError("analyze_normal_modes must return a dict")
        missing = [key for key in REQUIRED if key not in result]
        if missing:
            raise KeyError(f"missing result keys: {missing}")
        return {"name": case["name"], "result": encode(result)}
    except Exception as exc:
        return {"name": case.get("name"), "error": type(exc).__name__}


def main():
    request = json.load(sys.stdin)
    json.dump(
        {"cases": [run_one(case) for case in request["cases"]]},
        sys.stdout, allow_nan=False, separators=(",", ":"),
    )


if __name__ == "__main__":
    main()

