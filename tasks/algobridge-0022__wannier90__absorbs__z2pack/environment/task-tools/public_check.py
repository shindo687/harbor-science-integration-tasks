#!/usr/bin/env python3
"""Run the five published examples against their locked expected results."""

from __future__ import annotations

import json
from pathlib import Path
import sys


sys.path.insert(0, "/opt/task-tools")
from candidate_runner import run_candidate  # noqa: E402


def circle(x: float, y: float) -> float:
    delta = abs(float(x) - float(y)) % 1.0
    return min(delta, 1.0 - delta)


def matches(expected: dict, actual: dict) -> bool:
    if expected.get("status") != actual.get("status"):
        return False
    if expected.get("status") != "ok":
        return True
    if expected.get("z2") != actual.get("z2"):
        return False
    try:
        for erow, arow in zip(expected["wcc"], actual["wcc"], strict=True):
            direct = max(circle(x, y) for x, y in zip(erow, arow, strict=True))
            swapped = max(circle(x, y) for x, y in zip(erow, reversed(arow), strict=True))
            if min(direct, swapped) > 1e-6:
                return False
        if max(circle(x, y) for x, y in zip(
                expected["largest_gap_path"], actual["largest_gap_path"], strict=True)) > 1e-6:
            return False
        if max(abs(x - y) for x, y in zip(
                expected["largest_gap_size"], actual["largest_gap_size"], strict=True)) > 1e-6:
            return False
    except Exception:
        return False
    return True


def main() -> int:
    root = Path("/public-cases")
    inputs = sorted(root.glob("*.input.json"))
    passed = 0
    for input_path in inputs:
        expected_path = input_path.with_name(input_path.name.replace(".input.json", ".expected.json"))
        expected = json.loads(expected_path.read_text())
        try:
            actual = run_candidate(input_path)
            ok = matches(expected, actual)
        except Exception as exc:
            actual = {"error": str(exc)}
            ok = False
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {input_path.stem}: {actual.get('status', 'error')}")
    print(f"public examples: {passed}/{len(inputs)}")
    return 0 if passed == len(inputs) and len(inputs) == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())

