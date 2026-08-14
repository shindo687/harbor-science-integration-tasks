#!/usr/bin/env python3
"""Run one fixture through only the modified SciPy candidate."""

from __future__ import annotations

import json
import sys

import numpy as np
from scipy.stats import robust_linear_model


def run(spec):
    result = robust_linear_model(
        np.asarray(spec["x"], dtype=np.float64),
        np.asarray(spec["y"], dtype=np.float64),
        **spec.get("options", {}),
    )
    return {
        "name": spec["name"],
        "params": np.asarray(result.params).tolist(),
        "scale": float(result.scale),
        "weights": np.asarray(result.weights).tolist(),
        "covariance": np.asarray(result.covariance).tolist(),
        "residuals": np.asarray(result.residuals).tolist(),
        "history": {
            "objective": np.asarray(result.history["objective"]).tolist(),
            "scale": np.asarray(result.history["scale"]).tolist(),
            "params": np.asarray(result.history["params"]).tolist(),
        },
        "n_iter": int(result.n_iter),
        "converged": bool(result.converged),
    }


if __name__ == "__main__":
    print(json.dumps(run(json.load(sys.stdin)), allow_nan=False, sort_keys=True))

