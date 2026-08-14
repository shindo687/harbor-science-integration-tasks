#!/usr/bin/env python3
"""Run the five public MBAR examples against the submitted OpenMM source."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


EXAMPLE_ROOT = Path(__file__).resolve().parent
MODULE_PATH = Path("/testbed/wrappers/python/openmm/app/mbar.py")


def load_estimator():
    if not MODULE_PATH.is_file():
        raise FileNotFoundError(f"missing implementation: {MODULE_PATH}")
    spec = importlib.util.spec_from_file_location("openmm_public_mbar", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.estimate_mbar


def close(expected, observed, atol, rtol):
    left = np.asarray(expected, dtype=float)
    right = np.asarray(observed, dtype=float)
    return left.shape == right.shape and np.all(np.isfinite(right)) and np.allclose(
        left, right, atol=atol, rtol=rtol
    )


def main():
    estimate_mbar = load_estimator()
    passed = 0
    paths = sorted(EXAMPLE_ROOT.glob("[0-9][0-9]-*.json"))
    for path in paths:
        fixture = json.loads(path.read_text())
        case = fixture["input"]
        expected = fixture["expected"]
        result = estimate_mbar(
            case["u_kn"], case["N_k"], initial_f_k=case.get("initial_f_k"),
            relative_tolerance=case["relative_tolerance"],
            maximum_iterations=case["maximum_iterations"],
        )
        ok = (
            close(expected["f_k"], result["f_k"], 3e-8, 2e-9)
            and close(expected["Delta_f"], result["Delta_f"], 3e-8, 2e-9)
            and close(expected["dDelta_f"], result["dDelta_f"], 3e-5, 3e-6)
            and close(expected["overlap"], result["overlap"], 3e-7, 3e-7)
            and close(expected["effective_sample_number"],
                      result["effective_sample_number"], 3e-5, 3e-7)
            and bool(result["converged"])
            and float(result["residual"]) <= 5e-8
        )
        print(f"{path.stem}: {'PASS' if ok else 'FAIL'}")
        passed += int(ok)
    print(f"public examples: {passed}/{len(paths)}")
    return 0 if paths and passed == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())

