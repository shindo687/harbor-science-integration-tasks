#!/usr/bin/env python3
"""Generate five public fixtures only through the locked XGBoost reference."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


sys.path.insert(0, "/repo/tests")
from reference_runner import run_case  # noqa: E402
from model import jsonify  # noqa: E402


OUTPUT = Path("/output")


def params(objective="squared_error", **overrides):
    values = {
        "objective": objective,
        "n_estimators": 3,
        "max_depth": 2,
        "learning_rate": 0.3,
        "reg_lambda": 1.0,
        "reg_alpha": 0.0,
        "min_split_loss": 0.0,
    }
    values.update(overrides)
    return values


def clean(value):
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, list):
        return [clean(item) for item in value]
    if isinstance(value, float) and np.isnan(value):
        return None
    return value


def public_cases():
    axis = np.linspace(-1.8, 1.8, 10)
    regression_X = np.column_stack([axis, np.cos(axis * 1.3)])
    regression_y = np.where(axis < -0.4, -1.0, np.where(axis < 0.8, 0.5, 1.8))

    weighted_X = np.column_stack([
        np.arange(9, dtype=float),
        np.array([0, 1, 0, 1, 0, 1, 0, 1, 0], float),
    ])
    weighted_y = np.array([-2, -2, -1, 0, 0, 1, 2, 3, 3], float)

    missing_X = np.array([
        [-2.0, 0.0], [-1.0, 0.2], [0.0, 0.4], [1.0, 0.6],
        [2.0, 0.8], [np.nan, 0.1], [np.nan, 0.9], [3.0, 1.0],
    ])
    missing_y = np.array([-2, -1, 0, 1, 2, 2, 2, 3], float)

    logistic_X = np.array([
        [-1.5, -0.2], [-1.0, 0.5], [-0.7, -0.8], [-0.3, 1.1],
        [0.1, -0.5], [0.4, 0.4], [0.8, -1.0], [1.2, 0.2],
        [1.5, 1.0], [2.0, -0.2], [np.nan, 0.7], [np.nan, -0.4],
    ])
    logistic_y = np.array([0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 0], float)

    l1_X = np.arange(10, dtype=float).reshape(-1, 1)
    l1_y = np.array([-3, -3, -3, -0.03, 0.03, -0.03, 0.03, 2, 2, 2], float)

    return [
        {
            "name": "public_regression",
            "X": clean(regression_X), "y": clean(regression_y),
            "params": params(n_estimators=3, max_depth=2),
            "test_X": [[-2.0, 0.1], [-0.1, 0.9], [1.4, -0.2]],
        },
        {
            "name": "public_weighted",
            "X": clean(weighted_X), "y": clean(weighted_y),
            "sample_weight": [1, 2, 1, 3, 1, 2, 1, 2, 4],
            "params": params(n_estimators=4, max_depth=2,
                             learning_rate=0.25, reg_lambda=0.7),
        },
        {
            "name": "public_missing_direction",
            "X": clean(missing_X), "y": clean(missing_y),
            "params": params(n_estimators=3, max_depth=2),
            "test_X": [[None, 0.5], [-1.5, 0.5], [2.5, 0.5]],
        },
        {
            "name": "public_logistic",
            "X": clean(logistic_X), "y": clean(logistic_y),
            "params": params("logistic", n_estimators=4, max_depth=2,
                             learning_rate=0.2),
        },
        {
            "name": "public_l1_regularization",
            "X": clean(l1_X), "y": clean(l1_y),
            "params": params(n_estimators=2, max_depth=2,
                             reg_lambda=0.5, reg_alpha=0.35),
        },
    ]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT.glob("[0-9][0-9]-*.json"):
        old.unlink()
    for index, case in enumerate(public_cases(), start=1):
        result = run_case(case)
        path = OUTPUT / f"{index:02d}-{case['name']}.json"
        path.write_text(
            json.dumps(
                {"input": case, "expected": jsonify(result)},
                indent=2, allow_nan=False,
            ) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
