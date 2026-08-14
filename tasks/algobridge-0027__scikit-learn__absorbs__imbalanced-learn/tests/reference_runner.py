#!/usr/bin/env python3
"""Run the locked scikit-learn -> imbalanced-learn SMOTE reference."""

from __future__ import annotations

import json
import sys

import imblearn
from imblearn.over_sampling import SMOTE
from imblearn.over_sampling._smote.base import BaseSMOTE
import numpy as np
import sklearn


def decode_strategy(spec):
    kind = spec["kind"]
    if kind == "str":
        return spec["value"]
    if kind == "dict":
        return {item[0]: int(item[1]) for item in spec["items"]}
    if kind == "float":
        return float(spec["value"])
    raise ValueError(f"unknown strategy kind: {kind}")


def json_scalar(value):
    return value.item() if isinstance(value, np.generic) else value


def run_case(spec):
    X = np.asarray(spec["X"], dtype=np.dtype(spec["dtype"]))
    y = np.asarray(spec["y"])
    sample_weight = spec.get("sample_weight")
    if sample_weight is not None:
        sample_weight = np.asarray(sample_weight, dtype=float)

    traces = []
    original_generate = BaseSMOTE._generate_samples

    def traced_generate(
        self, X_class, nn_data, nn_num, rows, cols, steps, y_type=None, y=None
    ):
        class_indices = np.flatnonzero(np.equal(y_input, y_type))
        neighbor_rows = nn_num[rows, cols]
        traces.extend(
            (
                int(class_indices[parent]),
                int(class_indices[neighbor]),
                float(step),
            )
            for parent, neighbor, step in zip(
                rows, neighbor_rows, np.asarray(steps).reshape(-1), strict=True
            )
        )
        return original_generate(
            self, X_class, nn_data, nn_num, rows, cols, steps, y_type, y
        )

    y_input = y
    BaseSMOTE._generate_samples = traced_generate
    try:
        sampler = SMOTE(
            sampling_strategy=decode_strategy(spec["strategy"]),
            k_neighbors=int(spec["k_neighbors"]),
            random_state=int(spec["random_state"]),
        )
        X_resampled, y_resampled = sampler.fit_resample(X, y)
    finally:
        BaseSMOTE._generate_samples = original_generate

    parents = [[left, right] for left, right, _ in traces]
    lambdas = [step for _, _, step in traces]
    if sample_weight is None:
        weights = None
    else:
        synthetic_weights = [
            (1.0 - step) * sample_weight[left] + step * sample_weight[right]
            for left, right, step in traces
        ]
        weights = np.concatenate([sample_weight, synthetic_weights]).tolist()

    strategy = [
        [json_scalar(label), int(count)]
        for label, count in sampler.sampling_strategy_.items()
    ]
    return {
        "name": spec["name"],
        "X": np.asarray(X_resampled).tolist(),
        "y": [json_scalar(value) for value in np.asarray(y_resampled)],
        "X_dtype": str(np.asarray(X_resampled).dtype),
        "y_dtype": str(np.asarray(y_resampled).dtype),
        "sampling_strategy": strategy,
        "parent_indices": parents,
        "lambdas": lambdas,
        "sample_weight": weights,
    }


def main():
    payload = json.load(sys.stdin)
    results = [run_case(spec) for spec in payload["cases"]]
    json.dump(
        {
            "provenance": {
                "sklearn_version": sklearn.__version__,
                "sklearn_file": sklearn.__file__,
                "imblearn_version": imblearn.__version__,
                "imblearn_file": imblearn.__file__,
                "numpy_version": np.__version__,
            },
            "results": results,
        },
        sys.stdout,
        allow_nan=False,
    )


if __name__ == "__main__":
    main()
