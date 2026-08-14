#!/usr/bin/env python3
"""Compute fresh locked sklearn -> locked SHAP TreeExplainer references."""

from __future__ import annotations

import json
import sys

import numpy as np
import shap
import sklearn

from protocol import build_case, normalize_reference, raw_predictions, used_features


def run_case(spec):
    estimator, X = build_case(spec)
    explainer = shap.TreeExplainer(
        estimator,
        feature_perturbation="tree_path_dependent",
        model_output="raw",
    )
    values = explainer.shap_values(X, check_additivity=True)
    predictions = raw_predictions(estimator, X)
    values, base, predictions = normalize_reference(
        estimator, values, explainer.expected_value, predictions, spec.get("output")
    )
    return {
        "name": spec["name"],
        "values": np.asarray(values, dtype=float).tolist(),
        "base_values": np.asarray(base, dtype=float).tolist(),
        "predictions": np.asarray(predictions, dtype=float).tolist(),
        "used_features": used_features(estimator),
        "n_features": int(estimator.n_features_in_),
    }


def main():
    payload = json.load(sys.stdin)
    json.dump(
        {
            "provenance": {
                "sklearn_version": sklearn.__version__,
                "sklearn_file": sklearn.__file__,
                "shap_version": shap.__version__,
                "shap_file": shap.__file__,
                "numpy_version": np.__version__,
            },
            "results": [run_case(spec) for spec in payload["cases"]],
        },
        sys.stdout,
        allow_nan=False,
    )


if __name__ == "__main__":
    main()

