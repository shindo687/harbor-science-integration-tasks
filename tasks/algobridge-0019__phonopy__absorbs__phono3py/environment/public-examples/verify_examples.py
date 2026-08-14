#!/usr/bin/env python3
"""Replay public FC3 fixtures against the submitted phonopy module."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import numpy as np
from phonopy.harmonic.third_order import fit_fc3
from phonopy.structure.atoms import PhonopyAtoms


ROOT = Path(__file__).resolve().parent


def close(expected, observed, tolerance):
    left = np.asarray(expected, dtype=float)
    right = np.asarray(observed, dtype=float)
    return (
        left.shape == right.shape
        and np.all(np.isfinite(right))
        and np.allclose(left, right, atol=tolerance, rtol=tolerance)
    )


def run_one(item):
    specification = item["cell"]
    cell = PhonopyAtoms(
        symbols=specification["symbols"],
        cell=specification["cell"],
        scaled_positions=specification["scaled_positions"],
    )
    return fit_fc3(
        cell,
        np.asarray(item["displacements"], dtype=float),
        np.asarray(item["forces"], dtype=float),
        **item["arguments"],
    )


def matches(expected, observed):
    arrays = {
        "fc2": 2e-7,
        "fc3": 2e-7,
        "predicted_forces": 2e-8,
        "singular_values": 2e-8,
    }
    if not all(close(expected[key], observed[key], tolerance)
               for key, tolerance in arrays.items()):
        return False
    if any(int(expected[key]) != int(observed[key]) for key in (
            "rank", "n_parameters", "symmetry_operation_count")):
        return False
    return all(
        math.isfinite(float(observed[key]))
        and math.isclose(
            float(expected[key]),
            float(observed[key]),
            rel_tol=2e-8,
            abs_tol=2e-8,
        )
        for key in ("condition_number", "residual_norm")
    )


def main():
    paths = sorted(ROOT.glob("[0-9][0-9]-*.json"))
    passed = 0
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        observed = run_one(fixture["input"])
        ok = matches(fixture["expected"], observed)
        print(f"{path.stem}: {'PASS' if ok else 'FAIL'}")
        passed += int(ok)
    print(f"public examples: {passed}/{len(paths)}")
    return 0 if paths and passed == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())
