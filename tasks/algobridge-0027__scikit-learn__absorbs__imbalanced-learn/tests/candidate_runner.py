#!/usr/bin/env python3
"""Public-protocol runner installed outside verifier-private paths."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import pathlib
import sys
import traceback

import numpy as np


def decode_strategy(spec):
    if spec["kind"] == "str":
        return spec["value"]
    if spec["kind"] == "dict":
        return {item[0]: int(item[1]) for item in spec["items"]}
    if spec["kind"] == "float":
        return float(spec["value"])
    raise ValueError(f"unknown strategy kind: {spec['kind']}")


def json_scalar(value):
    return value.item() if isinstance(value, np.generic) else value


def run_case(SMOTE, spec):
    X = np.asarray(spec["X"], dtype=np.dtype(spec["dtype"]))
    y = np.asarray(spec["y"])
    sample_weight = spec.get("sample_weight")
    if sample_weight is not None:
        sample_weight = np.asarray(sample_weight, dtype=float)

    sampler = SMOTE(
        sampling_strategy=decode_strategy(spec["strategy"]),
        k_neighbors=int(spec["k_neighbors"]),
        random_state=int(spec["random_state"]),
    )
    with contextlib.redirect_stdout(io.StringIO()):
        X_resampled, y_resampled = sampler.fit_resample(
            X, y, sample_weight=sample_weight
        )

    X_resampled = np.asarray(X_resampled)
    y_resampled = np.asarray(y_resampled)
    synthetic_count = len(X_resampled) - len(X)
    parents = np.asarray(sampler.parent_indices_)
    lambdas = np.asarray(sampler.lambdas_)
    if parents.shape != (synthetic_count, 2):
        raise ValueError(f"parent_indices_ has shape {parents.shape}")
    if lambdas.shape != (synthetic_count,):
        raise ValueError(f"lambdas_ has shape {lambdas.shape}")
    if int(getattr(sampler, "n_features_in_", -1)) != X.shape[1]:
        raise ValueError("n_features_in_ is missing or incorrect")

    output_weight = sampler.sample_weight_resampled_
    if sample_weight is None:
        if output_weight is not None:
            raise ValueError("sample_weight_resampled_ must be None without weights")
        weights = None
    else:
        output_weight = np.asarray(output_weight, dtype=float)
        if output_weight.shape != (len(X_resampled),):
            raise ValueError("sample_weight_resampled_ has incorrect shape")
        weights = output_weight.tolist()

    strategy = [
        [json_scalar(label), int(count)]
        for label, count in sampler.sampling_strategy_.items()
    ]
    return {
        "name": spec["name"],
        "X": X_resampled.tolist(),
        "y": [json_scalar(value) for value in y_resampled],
        "X_dtype": str(X_resampled.dtype),
        "y_dtype": str(y_resampled.dtype),
        "sampling_strategy": strategy,
        "parent_indices": parents.astype(int).tolist(),
        "lambdas": lambdas.astype(float).tolist(),
        "sample_weight": weights,
    }


def contract_checks(SMOTE):
    from scipy import sparse
    from sklearn.base import clone

    X = np.asarray([[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [8.0, 8.0]])
    y = np.asarray([0, 0, 0, 1])
    probes = [
        ("nonpositive_k", lambda: SMOTE(k_neighbors=0).fit_resample(X, y)),
        ("too_few_minority", lambda: SMOTE(k_neighbors=2).fit_resample(X, y)),
        ("single_class", lambda: SMOTE(k_neighbors=1).fit_resample(X[:3], [0, 0, 0])),
        (
            "multiclass_float_strategy",
            lambda: SMOTE(sampling_strategy=0.8, k_neighbors=1).fit_resample(
                np.vstack([X, [[9.0, 9.0], [9.0, 8.0]]]),
                [0, 0, 1, 1, 2, 2],
            ),
        ),
        (
            "dict_below_current_count",
            lambda: SMOTE(sampling_strategy={0: 2}, k_neighbors=1).fit_resample(X, y),
        ),
        (
            "nonfinite_X",
            lambda: SMOTE(k_neighbors=1).fit_resample(
                [[0.0, 0.0], [1.0, float("nan")], [8.0, 8.0], [9.0, 9.0]],
                [0, 0, 1, 1],
            ),
        ),
        (
            "sparse_X",
            lambda: SMOTE(k_neighbors=1).fit_resample(
                sparse.csr_matrix([[0.0, 0.0], [1.0, 0.0], [8.0, 8.0], [9.0, 9.0]]),
                [0, 0, 1, 1],
            ),
        ),
    ]
    checks = []
    for name, probe in probes:
        try:
            probe()
        except Exception:
            checks.append({"name": name, "rejected": True})
        else:
            checks.append({"name": name, "rejected": False})
    clone_ok = isinstance(clone(SMOTE(k_neighbors=2, random_state=3)), SMOTE)
    checks.append({"name": "sklearn_clone", "rejected": clone_ok})
    return checks


def main():
    payload = json.load(sys.stdin)
    try:
        sys.path.insert(0, "/opt/candidate-runtime")
        import sklearn
        from sklearn.preprocessing import SMOTE

        module_spec = importlib.util.find_spec("sklearn.preprocessing._smote")
        donor_spec = importlib.util.find_spec("imblearn")
        if donor_spec is not None:
            raise RuntimeError("imbalanced-learn is importable in Candidate runtime")
        if module_spec is None or not str(module_spec.origin).startswith(
            "/opt/candidate-runtime/"
        ):
            raise RuntimeError("SMOTE implementation is not in Candidate runtime")
        isolation_checks = {
            "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
            "reference_runner_unreadable": not os.access(
                "/opt/reference-runner/reference_runner.py", os.R_OK
            ),
            "reference_host_removed": not pathlib.Path("/opt/reference-host").exists(),
            "reference_donor_removed": not pathlib.Path("/opt/reference-donor").exists(),
            "reference_venv_removed": not pathlib.Path("/opt/reference-venv").exists(),
            "pristine_host_removed": not pathlib.Path("/opt/pristine-host").exists(),
            "wheelhouse_removed": not pathlib.Path("/opt/wheels").exists(),
        }
        results = []
        for spec in payload["cases"]:
            try:
                results.append({"ok": True, "result": run_case(SMOTE, spec)})
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
            "smote_module": module_spec.origin,
            "results": results,
            "contract_checks": contract_checks(SMOTE),
            "isolation_checks": isolation_checks,
        }
    except Exception as error:
        response = {
            "fatal": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(limit=5),
            "results": [],
            "contract_checks": [],
            "isolation_checks": {},
        }
    json.dump(response, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
