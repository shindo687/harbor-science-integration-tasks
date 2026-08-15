#!/usr/bin/env python3
"""Run the five disclosed differential examples without exposing verifier code."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys


sys.path.insert(0, "/opt/task-tools")
from candidate_runner import run_candidate  # noqa: E402


def upper(matrix: list[list[float]]) -> list[float]:
    return [matrix[i][j] for i in range(len(matrix)) for j in range(i + 1, len(matrix))]


def correlation(left: list[float], right: list[float]) -> float:
    lm = sum(left) / len(left)
    rm = sum(right) / len(right)
    numerator = sum((a - lm) * (b - rm) for a, b in zip(left, right))
    denominator = math.sqrt(sum((a - lm) ** 2 for a in left) * sum((b - rm) ** 2 for b in right))
    return numerator / denominator


def top(matrix: list[list[float]]) -> set[tuple[int, int]]:
    length = len(matrix)
    ranked = sorted(
        ((matrix[i][j], i + 1, j + 1) for i in range(length) for j in range(i + 5, length)),
        key=lambda item: (-item[0], item[1], item[2]),
    )
    return {(i, j) for _, i, j in ranked[: max(1, length // 2)]}


def main() -> int:
    binary = Path("/testbed/hhcontacts")
    if not binary.is_file():
        build = subprocess.run(
            ["g++", "-std=c++11", "-O3", "-Wall", "-Wextra", "-pedantic",
             "/testbed/src/hhcontacts.cpp", "-o", str(binary)],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False,
        )
        if build.returncode:
            print(build.stdout, file=sys.stderr)
            return 2
        binary.chmod(0o755)
    failures = 0
    for path in sorted(Path("/examples").glob("*.json")):
        example = json.loads(path.read_text(encoding="utf-8"))
        expected = example["expected"]
        observed = run_candidate(example["packet"])
        raw_corr = correlation(upper(expected["raw_score"]), upper(observed["raw_score"]))
        apc_corr = correlation(upper(expected["apc_score"]), upper(observed["apc_score"]))
        overlap = len(top(expected["apc_score"]) & top(observed["apc_score"])) / len(top(expected["apc_score"]))
        objective_error = abs(expected["diagnostics"]["objective"] - observed["diagnostics"]["objective"])
        passed = raw_corr >= 0.999 and apc_corr >= 0.999 and overlap >= 0.95 and objective_error <= 1e-5
        failures += not passed
        print(f"{path.stem}: {'PASS' if passed else 'FAIL'} raw={raw_corr:.9f} "
              f"apc={apc_corr:.9f} top={overlap:.3f} objective_error={objective_error:.3g}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
