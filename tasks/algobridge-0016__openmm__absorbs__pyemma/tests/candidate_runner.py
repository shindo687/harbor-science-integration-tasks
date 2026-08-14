#!/usr/bin/env python3
"""Immutable JSON protocol runner for the submitted OpenMM API."""

from __future__ import annotations

import json
import math
import sys

import numpy as np
from openmm.app.markov_model import estimate_markov_model


REQUIRED = (
    "active_set", "count_matrix", "transition_matrix",
    "stationary_distribution", "eigenvalues", "timescales",
)


def finite_float(value):
    value = float(value)
    return value if math.isfinite(value) else None


def encode_eigenvalues(values):
    array = np.asarray(values)
    if array.ndim == 2 and array.shape[1] == 2 and not np.iscomplexobj(array):
        return [[finite_float(row[0]), finite_float(row[1])] for row in array]
    array = np.asarray(values, dtype=complex).reshape(-1)
    return [[finite_float(value.real), finite_float(value.imag)] for value in array]


def encode(result):
    return {
        "active_set": np.asarray(result["active_set"], dtype=int).tolist(),
        "count_matrix": np.asarray(result["count_matrix"]).tolist(),
        "transition_matrix": np.asarray(result["transition_matrix"], dtype=float).tolist(),
        "stationary_distribution": np.asarray(
            result["stationary_distribution"], dtype=float
        ).tolist(),
        "eigenvalues": encode_eigenvalues(result["eigenvalues"]),
        "timescales": [None if value is None else finite_float(value)
                       for value in result["timescales"]],
    }


def run_one(case):
    try:
        result = estimate_markov_model(
            case["trajectories"], lag=case.get("lag", 1),
            count_mode=case.get("count_mode", "sliding"),
            reversible=case.get("reversible", True),
            connectivity=case.get("connectivity", "largest"),
        )
        if not isinstance(result, dict):
            raise TypeError("estimate_markov_model must return a dict")
        missing = [key for key in REQUIRED if key not in result]
        if missing:
            raise KeyError(f"missing result keys: {missing}")
        return {"name": case["name"], "result": encode(result)}
    except Exception as exc:
        return {"name": case.get("name"), "error": type(exc).__name__}


def main():
    request = json.load(sys.stdin)
    json.dump({"cases": [run_one(case) for case in request["cases"]]},
              sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()

