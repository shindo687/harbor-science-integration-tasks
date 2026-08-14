#!/usr/bin/env python3
"""Run one fixture through the original locked SciPy + statsmodels path."""

from __future__ import annotations

import json
import sys

import numpy as np
from statsmodels.robust.norms import HuberT
from statsmodels.robust.robust_linear_model import RLM
from statsmodels.robust.scale import HuberScale


def run(spec):
    x = np.asarray(spec["x"], dtype=np.float64)
    y = np.asarray(spec["y"], dtype=np.float64)
    options = dict(spec.get("options", {}))
    fit_intercept = options.get("fit_intercept", True)
    design = np.column_stack((np.ones(y.size), x)) if fit_intercept else x

    frequencies = np.asarray(
        options.get("case_weights", np.ones(y.size)), dtype=np.int64,
    )
    expanded_design = np.repeat(design, frequencies, axis=0)
    expanded_y = np.repeat(y, frequencies)
    first = np.cumsum(np.r_[0, frequencies[:-1]])

    scale_name = options.get("scale", "mad").lower()
    scale_estimator = "mad" if scale_name == "mad" else HuberScale()
    result = RLM(
        expanded_y,
        expanded_design,
        M=HuberT(t=float(options.get("huber_t", 1.345))),
    ).fit(
        maxiter=int(options.get("maxiter", 50)),
        tol=float(options.get("tol", 1e-8)),
        scale_est=scale_estimator,
        cov=options.get("covariance", "H1").upper(),
        conv="dev",
    )

    objective = np.asarray(result.fit_history["deviance"][1:], dtype=float)
    scale_history = np.asarray(result.fit_history["scale"], dtype=float)
    params_history = np.asarray(result.fit_history["params"][1:], dtype=float)
    tolerance = float(options.get("tol", 1e-8))
    converged = bool(
        objective.size > 1 and abs(objective[-1] - objective[-2]) <= tolerance
    )
    original_residuals = y - design @ result.params
    return {
        "name": spec["name"],
        "params": np.asarray(result.params).tolist(),
        "scale": float(result.scale),
        "weights": np.asarray(result.weights)[first].tolist(),
        "covariance": np.asarray(result.cov_params()).tolist(),
        "residuals": original_residuals.tolist(),
        "history": {
            "objective": objective.tolist(),
            "scale": scale_history.tolist(),
            "params": params_history.tolist(),
        },
        "n_iter": int(result.fit_history["iteration"]),
        "converged": converged,
    }


if __name__ == "__main__":
    print(json.dumps(run(json.load(sys.stdin)), allow_nan=False, sort_keys=True))

