#!/usr/bin/env python3
"""Run the five public MSM examples against the submitted module."""

import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parent
MODULE = Path("/testbed/wrappers/python/openmm/app/markov_model.py")


def load_estimator():
    if not MODULE.is_file():
        raise FileNotFoundError(f"missing implementation: {MODULE}")
    spec = importlib.util.spec_from_file_location("openmm_public_markov", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.estimate_markov_model


def eigen_array(values):
    array = np.asarray(values)
    if array.ndim == 2 and array.shape[1] == 2 and not np.iscomplexobj(array):
        return array[:, 0] + 1j * array[:, 1]
    return np.asarray(values, dtype=complex).reshape(-1)


def close_times(expected, observed):
    if len(expected) != len(observed):
        return False
    return all(
        (left is None and right is None)
        or (left is not None and right is not None
            and math.isclose(float(left), float(right), rel_tol=1e-6, abs_tol=1e-6))
        for left, right in zip(expected, observed)
    )


def main():
    estimate = load_estimator()
    paths = sorted(ROOT.glob("[0-9][0-9]-*.json"))
    passed = 0
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        case, expected = fixture["input"], fixture["expected"]
        result = estimate(**case)
        transition = np.asarray(result["transition_matrix"], dtype=float)
        stationary = np.asarray(result["stationary_distribution"], dtype=float)
        ok = (
            np.array_equal(np.asarray(result["active_set"], dtype=int), expected["active_set"])
            and np.array_equal(np.asarray(result["count_matrix"]), expected["count_matrix"])
            and np.allclose(transition, expected["transition_matrix"], atol=2e-8, rtol=2e-8)
            and np.allclose(stationary, expected["stationary_distribution"], atol=2e-8, rtol=2e-8)
            and np.allclose(eigen_array(result["eigenvalues"]), eigen_array(expected["eigenvalues"]), atol=5e-7, rtol=5e-7)
            and close_times(expected["timescales"], result["timescales"])
            and np.allclose(transition.sum(axis=1), 1.0, atol=2e-9)
            and np.allclose(stationary @ transition, stationary, atol=2e-8, rtol=2e-8)
        )
        print(f"{path.stem}: {'PASS' if ok else 'FAIL'}")
        passed += int(ok)
    print(f"public examples: {passed}/{len(paths)}")
    return 0 if paths and passed == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())

