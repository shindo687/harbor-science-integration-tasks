#!/usr/bin/env python3
"""Verify the native implementation against published locked references."""

from __future__ import annotations

import json
import pathlib

import numpy as np
from sklearn.inspection import tree_shap

from protocol import build_case
from public_cases import public_cases


def main():
    expected = json.loads(pathlib.Path(__file__).with_name("expected.json").read_text())
    passed = 0
    for spec, reference in zip(public_cases(), expected["results"], strict=True):
        model, X = build_case(spec)
        actual = tree_shap(model, X, output=spec["output"])
        checks = [
            np.allclose(actual["values"], reference["values"], rtol=1e-9, atol=1e-9),
            np.allclose(actual["base_values"], reference["base_values"], rtol=1e-9, atol=1e-9),
            np.allclose(actual["predictions"], reference["predictions"], rtol=1e-12, atol=1e-12),
        ]
        ok = all(checks)
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {spec['name']}")
    print(f"public examples: {passed}/{len(expected['results'])}")
    if passed != len(expected["results"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

