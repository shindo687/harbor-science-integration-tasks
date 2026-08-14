#!/usr/bin/env python3
"""Replay public XGBoost-generated fixtures against the submitted estimator."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

import numpy as np

from sklearn.ensemble import SecondOrderGradientBoosting


ROOT = Path(__file__).resolve().parent


def close(left, right, atol, rtol):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    return (
        left.shape == right.shape
        and np.all(np.isfinite(right))
        and np.allclose(left, right, atol=atol, rtol=rtol)
    )


def tree_matches(expected, observed):
    if not isinstance(observed, dict):
        return False
    if ("leaf" in expected) != ("leaf" in observed):
        return False
    if any(int(observed.get(key, -1)) != int(expected[key])
           for key in ("node_id", "depth")):
        return False
    if not math.isclose(float(observed.get("cover", math.nan)),
                        float(expected["cover"]), abs_tol=2e-6, rel_tol=3e-7):
        return False
    if "leaf" in expected:
        return math.isclose(float(observed.get("leaf", math.nan)),
                            float(expected["leaf"]), abs_tol=2e-7, rel_tol=2e-7)
    if (observed.get("feature") != expected["feature"]
            or observed.get("missing") != expected["missing"]):
        return False
    if not math.isclose(float(observed.get("threshold", math.nan)),
                        float(expected["threshold"]), abs_tol=2e-7, rel_tol=2e-7):
        return False
    if not math.isclose(float(observed.get("gain", math.nan)),
                        float(expected["gain"]), abs_tol=5e-6, rel_tol=5e-6):
        return False
    return (tree_matches(expected["left"], observed.get("left"))
            and tree_matches(expected["right"], observed.get("right")))


def matches(fixture):
    case = fixture["input"]
    expected = fixture["expected"]
    X = np.asarray(case["X"], dtype=float)
    y = np.asarray(case["y"], dtype=float)
    test_X = np.asarray(case.get("test_X", case["X"]), dtype=float)
    weight = case.get("sample_weight")
    if weight is not None:
        weight = np.asarray(weight, dtype=float)
    estimator = SecondOrderGradientBoosting(**case["params"])
    estimator.fit(X, y, sample_weight=weight)
    trees_ok = (
        len(estimator.trees_) == len(expected["trees"])
        and all(tree_matches(left, right)
                for left, right in zip(expected["trees"], estimator.trees_))
    )
    margin = estimator.decision_function(test_X)
    return (
        trees_ok
        and close(expected["margin"], margin, 2e-7, 2e-7)
        and close(expected["prediction"], estimator.predict(test_X), 2e-7, 2e-7)
        and close(expected["feature_gains"], estimator.feature_gains_, 2e-5, 5e-7)
        and close(expected["training_loss"], estimator.training_loss_, 2e-8, 2e-8)
        and (
            case["params"]["objective"] != "logistic"
            or close(expected["probability"], estimator.predict_proba(test_X),
                     2e-7, 2e-7)
        )
    )


def main():
    paths = sorted(ROOT.glob("[0-9][0-9]-*.json"))
    passed = 0
    for path in paths:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        ok = matches(fixture)
        print(f"{path.stem}: {'PASS' if ok else 'FAIL'}")
        passed += int(ok)
    print(f"public examples: {passed}/{len(paths)}")
    return 0 if paths and passed == len(paths) else 1


if __name__ == "__main__":
    sys.exit(main())
