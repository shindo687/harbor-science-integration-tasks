#!/usr/bin/env python3
"""Run the submitted sklearn estimator on JSON cases."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

from model import jsonify


def run_case(case):
    from sklearn.ensemble import SecondOrderGradientBoosting

    X = np.asarray(case["X"], dtype=np.float64)
    y = np.asarray(case["y"], dtype=np.float64)
    test_X = np.asarray(case.get("test_X", case["X"]), dtype=np.float64)
    weight = case.get("sample_weight")
    if weight is not None:
        weight = np.asarray(weight, dtype=np.float64)
    estimator = SecondOrderGradientBoosting(**case["params"])
    estimator.fit(X, y, sample_weight=weight)
    margin = np.asarray(estimator.decision_function(test_X), dtype=float)
    probability = None
    if case["params"]["objective"] == "logistic":
        probability = np.asarray(estimator.predict_proba(test_X), dtype=float)
    return {
        "name": case["name"],
        "trees": estimator.trees_,
        "feature_gains": np.asarray(estimator.feature_gains_, dtype=float),
        "training_loss": np.asarray(estimator.training_loss_, dtype=float),
        "margin": margin,
        "prediction": np.asarray(estimator.predict(test_X)),
        "probability": probability,
        "n_features_in": int(estimator.n_features_in_),
    }


def main():
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    cases = json.loads(source.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        try:
            results.append(run_case(case))
        except Exception as error:  # reported to the trusted grader
            results.append(
                {
                    "name": case.get("name"),
                    "error_type": type(error).__name__,
                    "error": str(error)[:500],
                }
            )
    destination.write_text(
        json.dumps(jsonify({"cases": results}), allow_nan=False, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
