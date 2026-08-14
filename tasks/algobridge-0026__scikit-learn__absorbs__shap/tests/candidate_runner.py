#!/usr/bin/env python3
"""Public-protocol runner installed outside verifier-private paths."""

from __future__ import annotations

import importlib.util
import json
import os
import pathlib
import sys
import traceback

import numpy as np

from protocol import build_case, raw_predictions


def run_case(tree_shap, spec):
    estimator, X = build_case(spec)
    result = tree_shap(estimator, X, output=spec.get("output"))
    values = np.asarray(result["values"], dtype=float)
    base = np.asarray(result["base_values"], dtype=float)
    predictions = np.asarray(result["predictions"], dtype=float)
    truth = raw_predictions(estimator, X)
    if values.ndim == 2:
        local = values.sum(axis=1) + float(base.reshape(-1)[0])
    elif values.ndim == 3:
        local = values.sum(axis=1) + base
    else:
        raise ValueError(f"values has invalid shape {values.shape}")
    return {
        "name": spec["name"],
        "values": values.tolist(),
        "base_values": base.tolist(),
        "predictions": predictions.tolist(),
        "local_accuracy_error": float(np.max(np.abs(local - predictions))),
        "raw_prediction_shape": list(np.asarray(truth).shape),
    }


def contract_checks(tree_shap):
    from scipy import sparse
    from sklearn.base import clone
    from sklearn.linear_model import LinearRegression
    from sklearn.tree import DecisionTreeRegressor

    X = np.asarray([[0.0, 0.0], [1.0, 0.5], [2.0, -1.0], [3.0, 2.0]])
    y = np.asarray([0.0, 1.0, 1.5, 4.0])
    fitted = DecisionTreeRegressor(max_depth=2, random_state=0).fit(X, y)
    categorical = DecisionTreeRegressor(
        max_depth=2, random_state=0, categorical_features=[0]
    ).fit(X, y)
    probes = [
        ("unfitted", lambda: tree_shap(DecisionTreeRegressor(), X)),
        ("unsupported_estimator", lambda: tree_shap(LinearRegression().fit(X, y), X)),
        ("sparse_X", lambda: tree_shap(fitted, sparse.csr_matrix(X))),
        ("wrong_features", lambda: tree_shap(fitted, X[:, :1])),
        ("invalid_output", lambda: tree_shap(fitted, X, output=4)),
        ("categorical_split", lambda: tree_shap(categorical, X)),
    ]
    checks = []
    for name, probe in probes:
        try:
            probe()
        except Exception:
            checks.append({"name": name, "rejected": True})
        else:
            checks.append({"name": name, "rejected": False})
    checks.append({"name": "host_clone_regression", "rejected": clone(fitted) is not fitted})
    checks.append(
        {
            "name": "public_docstring",
            "rejected": bool(tree_shap.__doc__)
            and "path-dependent" in tree_shap.__doc__.lower(),
        }
    )
    return checks


def main():
    payload = json.load(sys.stdin)
    try:
        sys.path.insert(0, "/opt/candidate-runtime")
        import sklearn
        from sklearn.inspection import tree_shap

        module_spec = importlib.util.find_spec(tree_shap.__module__)
        donor_spec = importlib.util.find_spec("shap")
        if donor_spec is not None:
            raise RuntimeError("SHAP is importable in Candidate runtime")
        if module_spec is None or not str(module_spec.origin).startswith(
            "/opt/candidate-runtime/"
        ):
            raise RuntimeError("tree_shap implementation is not in Candidate runtime")
        isolation_checks = {
            "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
            "reference_runner_removed": not pathlib.Path("/opt/reference-runner").exists(),
            "reference_source_removed": not pathlib.Path("/opt/reference-donor").exists(),
            "reference_venv_removed": not pathlib.Path("/opt/reference-venv").exists(),
            "pristine_host_removed": not pathlib.Path("/opt/pristine-host").exists(),
            "wheelhouses_removed": not pathlib.Path("/opt/wheels").exists()
            and not pathlib.Path("/opt/reference-wheels").exists(),
            "candidate_tools_removed": not pathlib.Path("/opt/candidate-tools").exists(),
        }
        results = []
        for spec in payload["cases"]:
            try:
                results.append({"ok": True, "result": run_case(tree_shap, spec)})
            except Exception as error:
                results.append(
                    {
                        "ok": False,
                        "name": spec.get("name"),
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
        response = {
            "fatal": None,
            "sklearn_file": sklearn.__file__,
            "sklearn_version": sklearn.__version__,
            "tree_shap_module": module_spec.origin,
            "results": results,
            "contract_checks": contract_checks(tree_shap),
            "isolation_checks": isolation_checks,
        }
    except Exception as error:
        response = {
            "fatal": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(limit=6),
            "results": [],
            "contract_checks": [],
            "isolation_checks": {},
        }
    json.dump(response, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
