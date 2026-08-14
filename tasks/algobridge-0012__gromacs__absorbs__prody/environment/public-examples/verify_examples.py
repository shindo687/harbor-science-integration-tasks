#!/usr/bin/env python3
"""Replay public ANM fixtures against the submitted gmxapi module."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parent
MODULE = Path(
    "/testbed/python_packaging/gmxapi/src/gmxapi/analysis/anm.py"
)


def load_api():
    specification = importlib.util.spec_from_file_location(
        "gmxapi_public_anm", MODULE
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.analyze_anm


def close(expected, observed, tolerance):
    left = np.asarray(expected, dtype=float)
    right = np.asarray(observed, dtype=float)
    return (
        left.shape == right.shape
        and np.all(np.isfinite(right))
        and np.allclose(left, right, atol=tolerance, rtol=tolerance)
    )


def matches(expected, observed):
    if not np.array_equal(
            np.asarray(expected["node_indices"], dtype=int),
            np.asarray(observed["node_indices"]),
    ):
        return False
    if any(int(expected[key]) != int(observed[key]) for key in (
            "zero_mode_count", "component_count")):
        return False
    expected_modes = np.asarray(expected["modes"], dtype=float)
    modes = np.asarray(observed["modes"], dtype=float)
    return (
        close(expected["hessian"], observed["hessian"], 2e-9)
        and close(expected["eigenvalues"], observed["eigenvalues"], 2e-8)
        and modes.shape == expected_modes.shape
        and close(expected_modes @ expected_modes.T,
                  modes @ modes.T, 3e-7)
        and close(expected["covariance"], observed["covariance"], 2e-7)
        and close(expected["msf"], observed["msf"], 2e-7)
        and close(expected["cross_correlation"],
                  observed["cross_correlation"], 8e-7)
    )


def main():
    analyze_anm = load_api()
    paths = sorted(ROOT.glob("[0-9][0-9]-*.json"))
    passed = 0
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        case = fixture["input"]
        observed = analyze_anm(
            np.asarray(case["coordinates_nm"], dtype=float),
            **case["arguments"],
        )
        ok = matches(fixture["expected"], observed)
        print(f"{path.stem}: {'PASS' if ok else 'FAIL'}")
        passed += int(ok)
    print(f"public examples: {passed}/{len(paths)}")
    return 0 if paths and passed == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())
