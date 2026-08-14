#!/usr/bin/env python3
"""Immutable candidate protocol runner."""

from __future__ import annotations

import json
import sys

import numpy as np
from openmm.app.mbar import estimate_mbar


REQUIRED = (
    "f_k", "Delta_f", "dDelta_f", "covariance", "weights", "overlap",
    "effective_sample_number", "iterations", "residual", "converged",
)


def encode(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    return value


def run_one(case):
    try:
        result = estimate_mbar(
            case["u_kn"], case["N_k"],
            initial_f_k=case.get("initial_f_k"),
            relative_tolerance=case.get("relative_tolerance", 1e-10),
            maximum_iterations=case.get("maximum_iterations", 10000),
        )
        if not isinstance(result, dict):
            raise TypeError("estimate_mbar must return a dict")
        missing = [key for key in REQUIRED if key not in result]
        if missing:
            raise KeyError(f"missing result keys: {missing}")
        return {"name": case.get("name"), "result": {
            key: encode(result[key]) for key in REQUIRED
        }}
    except Exception as exc:  # validation behavior is part of the protocol
        return {"name": case.get("name"), "error": type(exc).__name__}


def main():
    request = json.load(sys.stdin)
    json.dump({"cases": [run_one(case) for case in request["cases"]]},
              sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()

