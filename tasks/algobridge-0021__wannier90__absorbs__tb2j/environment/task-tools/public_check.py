#!/usr/bin/env python3
"""Run the five published examples against their locked expected results."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys


sys.path.insert(0, "/opt/task-tools")
from candidate_runner import run_candidate  # noqa: E402


def _flatten(value):
    if isinstance(value, list):
        for item in value:
            yield from _flatten(item)
    else:
        yield float(value)


def _error(expected, actual) -> float:
    try:
        left = list(_flatten(expected))
        right = list(_flatten(actual))
        if len(left) != len(right):
            return math.inf
        return max((abs(a - b) for a, b in zip(left, right)), default=0.0)
    except Exception:
        return math.inf


def matches(expected: dict, actual: dict) -> bool:
    if expected.get("status") != actual.get("status"):
        return False
    if expected.get("status") != "ok":
        return True
    return (
        expected.get("kmesh") == actual.get("kmesh")
        and expected.get("contour_points") == actual.get("contour_points")
        and expected.get("r_values") == actual.get("r_values")
        and _error(expected.get("exchange_ev"), actual.get("exchange_ev")) <= 2.0e-7
        and _error(expected.get("moments_z"), actual.get("moments_z")) <= 2.0e-8
        and abs(float(expected.get("integration_emin"))
                - float(actual.get("integration_emin"))) <= 2.0e-10
        and abs(float(expected.get("pair_reversal_max_error"))
                - float(actual.get("pair_reversal_max_error"))) <= 2.0e-7
    )


def main() -> int:
    root = Path("/public-cases")
    inputs = sorted(root.glob("*.input.json"))
    passed = 0
    for input_path in inputs:
        expected_path = input_path.with_name(
            input_path.name.replace(".input.json", ".expected.json")
        )
        expected = json.loads(expected_path.read_text())
        try:
            actual = run_candidate(input_path)
            ok = matches(expected, actual)
        except Exception as exc:
            actual = {"status": "error", "error": str(exc)}
            ok = False
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {input_path.stem}: "
              f"{actual.get('status', 'error')}")
    print(f"public examples: {passed}/{len(inputs)}")
    return 0 if passed == len(inputs) and len(inputs) == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
