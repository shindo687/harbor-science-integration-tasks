#!/usr/bin/env python3
"""Run public elastic-network fixtures against the submitted AlphaFold module."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
from alphafold.common import protein as af_protein
from alphafold.common.normal_modes import analyze_normal_modes


ROOT = Path(__file__).resolve().parent


def parse(item):
    if item["format"] == "pdb":
        return af_protein.from_pdb_string(item["structure"])
    return af_protein.from_mmcif_string(item["structure"])


def close(expected, observed, tolerance):
    left = np.asarray(expected, dtype=float)
    right = np.asarray(observed, dtype=float)
    return (
        left.shape == right.shape
        and np.all(np.isfinite(right))
        and np.allclose(left, right, atol=tolerance, rtol=tolerance)
    )


def main():
    paths = sorted(ROOT.glob("[0-9][0-9]-*.json"))
    passed = 0
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        item, expected = fixture["input"], fixture["expected"]
        result = analyze_normal_modes(parse(item), **item["arguments"])
        expected_modes = np.asarray(expected["modes"], dtype=float)
        modes = np.asarray(result["modes"], dtype=float)
        ok = (
            result["model"] == expected["model"]
            and result["residue_mapping"] == expected["residue_mapping"]
            and int(result["zero_mode_count"]) == int(expected["zero_mode_count"])
            and close(expected["network_matrix"], result["network_matrix"], 2e-10)
            and close(expected["eigenvalues"], result["eigenvalues"], 2e-7)
            and close(expected_modes @ expected_modes.T, modes @ modes.T, 5e-6)
            and close(expected["msf"], result["msf"], 5e-6)
            and close(expected["cross_correlation"],
                      result["cross_correlation"], 5e-6)
        )
        print(f"{path.stem}: {'PASS' if ok else 'FAIL'}")
        passed += int(ok)
    print(f"public examples: {passed}/{len(paths)}")
    return 0 if paths and passed == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())

