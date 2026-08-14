#!/usr/bin/env python3
"""Run the public examples against frozen reference outputs."""

from __future__ import annotations

import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from candidate_runner import run_case  # noqa: E402
from compare import compare_case  # noqa: E402
from task_cases import public_cases  # noqa: E402


def main():
    from scanpy.pp import batch_balanced_neighbors

    expected = json.loads((HERE / "expected.json").read_text())
    details = []
    for case, reference in zip(public_cases(), expected["results"], strict=True):
        candidate = run_case(batch_balanced_neighbors, case)
        passed, comparison = compare_case(reference, candidate)
        details.append({"name": case["name"], "passed": passed, **comparison})
    report = {
        "passed": sum(item["passed"] for item in details),
        "total": len(details),
        "cases": details,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

