#!/usr/bin/env python3
"""Run the submitted AlphaFold API against all disclosed examples."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

from alphafold.common.secondary_structure import assign_secondary_structure


AA = {
    "ALA": 0, "ARG": 1, "ASN": 2, "ASP": 3, "CYS": 4,
    "GLN": 5, "GLU": 6, "GLY": 7, "HIS": 8, "ILE": 9,
    "LEU": 10, "LYS": 11, "MET": 12, "PHE": 13, "PRO": 14,
    "SER": 15, "THR": 16, "TRP": 17, "TYR": 18, "VAL": 19,
}
ATOM = {"N": 0, "CA": 1, "C": 2, "O": 4}


def arrays(case):
    residues = case["residues"]
    n = len(residues)
    positions = np.zeros((n, 37, 3), dtype=float)
    mask = np.zeros((n, 37), dtype=float)
    kinds, numbers, chains = [], [], []
    chain_ids = {}
    for i, residue in enumerate(residues):
        kinds.append(AA[residue["residue_name"]])
        numbers.append(residue["residue_index"])
        chains.append(chain_ids.setdefault(residue["chain_id"], len(chain_ids)))
        for name, xyz in residue["atoms"].items():
            positions[i, ATOM[name]] = xyz
            mask[i, ATOM[name]] = 1
    return (positions, mask, np.asarray(kinds, dtype=np.int32),
            np.asarray(numbers, dtype=np.int32), np.asarray(chains, dtype=np.int32))


def compare(expected, observed):
    codes = observed["secondary_structure"]
    if isinstance(codes, str):
        codes = list(codes)
    if list(codes) != expected["secondary_structure"]:
        return False
    for key in ("acceptor_index", "donor_index"):
        if not np.array_equal(np.asarray(observed[key]), np.asarray(expected[key])):
            return False
    for key in ("acceptor_energy", "donor_energy"):
        if not np.allclose(np.asarray(observed[key], dtype=float),
                           np.asarray(expected[key], dtype=float),
                           atol=0.051, rtol=0):
            return False
    return True


def main():
    files = sorted(Path("/examples").glob("[0-9][0-9]-*.json"))
    failures = []
    for path in files:
        payload = json.loads(path.read_text())
        try:
            result = assign_secondary_structure(*arrays(payload["case"]))
            passed = compare(payload["expected"], result)
        except Exception as exc:
            passed = False
            print(f"FAIL {path.name}: {type(exc).__name__}")
        else:
            print(f"{'PASS' if passed else 'FAIL'} {path.name}")
        if not passed:
            failures.append(path.name)
    print(f"{len(files) - len(failures)}/{len(files)} public examples passed")
    return int(bool(failures))


if __name__ == "__main__":
    sys.exit(main())

