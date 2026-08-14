#!/usr/bin/env python3
"""Locked PyEMMA reference runner."""

from __future__ import annotations

import json
import math
import sys
import warnings

import numpy as np
import pyemma


def canonical_eigenvalues(values):
    values = [complex(value) for value in np.asarray(values).reshape(-1)]
    stationary = min(range(len(values)), key=lambda i: abs(values[i] - 1.0))
    first = values.pop(stationary)
    values.sort(key=lambda value: (-abs(value), -value.real, -value.imag))
    return [first, *values]


def encode_eigenvalues(values):
    return [[float(value.real), float(value.imag)] for value in values]


def timescales(values, lag):
    result = []
    for value in values[1:]:
        magnitude = abs(value)
        if magnitude <= 1e-14:
            result.append(0.0)
        elif abs(magnitude - 1.0) <= 1e-14:
            result.append(None)
        else:
            timescale = -float(lag) / math.log(magnitude)
            result.append(timescale if math.isfinite(timescale) else None)
    return result


def run_one(case):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model = pyemma.msm.estimate_markov_model(
            case["trajectories"], lag=case.get("lag", 1),
            count_mode=case.get("count_mode", "sliding"),
            reversible=case.get("reversible", True),
            connectivity=case.get("connectivity", "largest"),
        )
    eigenvalues = canonical_eigenvalues(model.eigenvalues())
    return {"name": case["name"], "result": {
        "active_set": np.asarray(model.active_set, dtype=int).tolist(),
        "count_matrix": np.asarray(model.count_matrix_active).tolist(),
        "transition_matrix": np.asarray(model.transition_matrix).tolist(),
        "stationary_distribution": np.asarray(
            model.stationary_distribution
        ).tolist(),
        "eigenvalues": encode_eigenvalues(eigenvalues),
        "timescales": timescales(eigenvalues, case.get("lag", 1)),
    }}


def main():
    request = json.load(sys.stdin)
    json.dump({"cases": [run_one(case) for case in request["cases"]]},
              sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
