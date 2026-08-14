#!/usr/bin/env python3
"""Offline checker for the five frozen public examples."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.stats import robust_linear_model

from public_cases import public_cases


ROOT = Path(__file__).resolve().parent


def close(left, right, tolerance):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    return left.shape == right.shape and np.allclose(
        left, right, rtol=tolerance, atol=tolerance,
    )


def main():
    expected = json.loads((ROOT / "expected.json").read_text())
    details = []
    for spec in public_cases():
        result = robust_linear_model(
            np.asarray(spec["x"], dtype=float),
            np.asarray(spec["y"], dtype=float),
            **spec.get("options", {}),
        )
        reference = expected[spec["name"]]
        checks = {
            "params": close(result.params, reference["params"], 1e-8),
            "scale": close(result.scale, reference["scale"], 1e-8),
            "weights": close(result.weights, reference["weights"], 1e-8),
            "covariance": close(result.covariance, reference["covariance"], 1e-6),
            "residuals": close(result.residuals, reference["residuals"], 1e-8),
            "objective": close(
                result.history["objective"],
                reference["history"]["objective"],
                1e-8,
            ),
            "n_iter": int(result.n_iter) == reference["n_iter"],
        }
        details.append({"name": spec["name"], "passed": all(checks.values()), "checks": checks})
    report = {
        "passed": sum(item["passed"] for item in details),
        "total": len(details),
        "details": details,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

