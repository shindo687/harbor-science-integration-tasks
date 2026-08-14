#!/usr/bin/env python3
"""Verify the native host implementation against published reference data."""

from __future__ import annotations

import json
import pathlib

import numpy as np
from sklearn.preprocessing import SMOTE

from public_cases import public_cases


def decode_strategy(spec):
    if spec["kind"] == "str":
        return spec["value"]
    if spec["kind"] == "dict":
        return {label: int(count) for label, count in spec["items"]}
    return float(spec["value"])


def run_case(spec):
    X = np.asarray(spec["X"], dtype=spec["dtype"])
    y = np.asarray(spec["y"])
    sample_weight = spec["sample_weight"]
    sampler = SMOTE(
        sampling_strategy=decode_strategy(spec["strategy"]),
        k_neighbors=spec["k_neighbors"],
        random_state=spec["random_state"],
    )
    X_result, y_result = sampler.fit_resample(
        X, y, sample_weight=sample_weight
    )
    return {
        "X": np.asarray(X_result).tolist(),
        "y": np.asarray(y_result).tolist(),
        "parent_indices": np.asarray(sampler.parent_indices_).tolist(),
        "lambdas": np.asarray(sampler.lambdas_).tolist(),
        "sample_weight": None
        if sampler.sample_weight_resampled_ is None
        else np.asarray(sampler.sample_weight_resampled_).tolist(),
    }


def main():
    expected = json.loads(
        pathlib.Path(__file__).with_name("expected.json").read_text()
    )["results"]
    passed = 0
    for spec, oracle in zip(public_cases(), expected, strict=True):
        actual = run_case(spec)
        exact = (
            actual["y"] == oracle["y"]
            and actual["parent_indices"] == oracle["parent_indices"]
        )
        numeric = (
            np.allclose(actual["X"], oracle["X"], rtol=0.0, atol=1e-12)
            and np.allclose(
                actual["lambdas"], oracle["lambdas"], rtol=0.0, atol=1e-15
            )
        )
        if actual["sample_weight"] is None or oracle["sample_weight"] is None:
            weights = actual["sample_weight"] is oracle["sample_weight"]
        else:
            weights = np.allclose(
                actual["sample_weight"],
                oracle["sample_weight"],
                rtol=0.0,
                atol=1e-12,
            )
        ok = exact and numeric and weights
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {spec['name']}")
    print(f"public examples: {passed}/{len(expected)}")
    if passed != len(expected):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
