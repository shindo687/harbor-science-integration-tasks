#!/usr/bin/env python3
"""Locked GROMACS-coordinate to ProDy ANM reference runner."""

from __future__ import annotations

import json
import sys
import warnings

import numpy as np
from prody import ANM, calcCrossCorr, calcSqFlucts

from model import adjacency, component_count, selected_coordinates


def jsonify(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonify(item) for item in value]
    return value


def run_one(case):
    coordinates_nm, indices = selected_coordinates(case)
    arguments = case["arguments"]
    model = ANM(case["name"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.buildHessian(
            coordinates_nm * 10.0,
            cutoff=float(arguments["cutoff_nm"]) * 10.0,
            gamma=float(arguments["gamma"]),
            kdtree=False,
        )
        model.calcModes(n_modes=int(arguments["n_modes"]))
        hessian = np.asarray(model.getHessian(), dtype=float)
        eigenvalues = np.asarray(model.getEigvals(), dtype=float)
        modes = np.asarray(model.getEigvecs(), dtype=float)
        covariance = np.asarray(model.getCovariance(), dtype=float)
        msf = np.asarray(calcSqFlucts(model), dtype=float)
        correlation = np.asarray(calcCrossCorr(model), dtype=float)
    all_eigenvalues = np.linalg.eigvalsh(hessian)
    graph = adjacency(coordinates_nm, arguments["cutoff_nm"])
    return {
        "node_indices": indices,
        "hessian": hessian,
        "zero_mode_count": int(np.sum(all_eigenvalues < 1e-6)),
        "component_count": component_count(graph),
        "eigenvalues": eigenvalues,
        "modes": modes,
        "covariance": covariance,
        "msf": msf,
        "cross_correlation": correlation,
    }


def main():
    request = json.load(sys.stdin)
    output = []
    for case in request["cases"]:
        try:
            output.append({
                "name": case["name"],
                "result": jsonify(run_one(case)),
            })
        except Exception as exc:
            output.append({
                "name": case["name"],
                "error": type(exc).__name__,
                "message": str(exc),
            })
    json.dump({"cases": output}, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
