#!/usr/bin/env python3
"""Immutable JSON adapter for the submitted AlphaFold secondary-structure API."""

from __future__ import annotations

import json
import sys

import numpy as np
from alphafold.common.secondary_structure import assign_secondary_structure


THREE_TO_INDEX = {
    "ALA": 0, "ARG": 1, "ASN": 2, "ASP": 3, "CYS": 4,
    "GLN": 5, "GLU": 6, "GLY": 7, "HIS": 8, "ILE": 9,
    "LEU": 10, "LYS": 11, "MET": 12, "PHE": 13, "PRO": 14,
    "SER": 15, "THR": 16, "TRP": 17, "TYR": 18, "VAL": 19,
}
ATOM_INDEX = {"N": 0, "CA": 1, "C": 2, "O": 4}
REQUIRED = (
    "secondary_structure", "acceptor_index", "acceptor_energy",
    "donor_index", "donor_energy",
)


def arrays(case):
    if "raw_arrays" in case:
        raw = case["raw_arrays"]
        return (
            np.asarray(raw["atom_positions"]),
            np.asarray(raw["atom_mask"]),
            np.asarray(raw["aatype"]),
            np.asarray(raw["residue_index"]),
            None if raw.get("chain_index") is None else np.asarray(raw["chain_index"]),
        )
    residues = case["residues"]
    n = len(residues)
    positions = np.zeros((n, 37, 3), dtype=float)
    mask = np.zeros((n, 37), dtype=float)
    aatype = np.empty(n, dtype=np.int32)
    residue_index = np.empty(n, dtype=np.int32)
    chain_index = np.empty(n, dtype=np.int32)
    chain_ids = {}
    for i, residue in enumerate(residues):
        aatype[i] = THREE_TO_INDEX[residue["residue_name"]]
        residue_index[i] = residue["residue_index"]
        chain = residue["chain_id"]
        chain_index[i] = chain_ids.setdefault(chain, len(chain_ids))
        for name, xyz in residue["atoms"].items():
            atom = ATOM_INDEX[name]
            positions[i, atom] = xyz
            mask[i, atom] = 1.0
    return positions, mask, aatype, residue_index, chain_index


def encode(result, n):
    if not isinstance(result, dict):
        raise TypeError("assign_secondary_structure must return a dict")
    missing = [key for key in REQUIRED if key not in result]
    if missing:
        raise KeyError(f"missing result keys: {missing}")
    codes = result["secondary_structure"]
    if isinstance(codes, str):
        codes = list(codes)
    codes = [str(value) for value in codes]
    if len(codes) != n:
        raise ValueError("secondary_structure has the wrong length")
    encoded = {"secondary_structure": codes}
    for key in ("acceptor_index", "donor_index"):
        value = np.asarray(result[key])
        if value.shape != (n, 2):
            raise ValueError(f"{key} must have shape [N, 2]")
        encoded[key] = value.astype(np.int64).tolist()
    for key in ("acceptor_energy", "donor_energy"):
        value = np.asarray(result[key], dtype=float)
        if value.shape != (n, 2) or not np.all(np.isfinite(value)):
            raise ValueError(f"{key} must be a finite [N, 2] array")
        encoded[key] = value.tolist()
    return encoded


def run_one(case):
    try:
        args = arrays(case)
        result = assign_secondary_structure(*args)
        n = len(args[2])
        return {"name": case.get("name"), "result": encode(result, n)}
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
