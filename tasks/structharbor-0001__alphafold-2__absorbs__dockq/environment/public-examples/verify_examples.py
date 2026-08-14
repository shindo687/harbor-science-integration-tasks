#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any


EXPECTED_KEYS = {
    "fnat", "iRMSD", "LRMSD", "DockQ", "CAPRI",
    "native_contacts", "preserved_contacts", "mapping",
}


def compare(actual: Any, expected: Any, *, atol: float, rtol: float, path: str) -> None:
    if isinstance(expected, bool) or isinstance(actual, bool):
        if actual is not expected:
            raise AssertionError(f"boolean mismatch at {path}")
    elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isfinite(float(actual)) or not math.isclose(
            float(actual), float(expected), abs_tol=atol, rel_tol=rtol
        ):
            raise AssertionError(f"numeric mismatch at {path}: {actual} != {expected}")
    elif isinstance(expected, dict) and isinstance(actual, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"key mismatch at {path}: {set(actual) ^ set(expected)}")
        for key in expected:
            compare(actual[key], expected[key], atol=atol, rtol=rtol,
                    path=f"{path}.{key}")
    elif actual != expected:
        raise AssertionError(f"value mismatch at {path}: {actual!r} != {expected!r}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {Path(sys.argv[0]).name} DOCKQ_SCORE.py")
    candidate_path = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location("public_dockq_candidate", candidate_path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot load {candidate_path}")
    candidate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(candidate)

    data = json.loads(Path(__file__).with_name("examples.json").read_text())
    atol = float(data["tolerance"]["absolute"])
    rtol = float(data["tolerance"]["relative"])
    for index, example in enumerate(data["examples"], 1):
        actual = candidate.score_complex(
            example["model"], data["native"], example["mapping"]
        )
        if not isinstance(actual, dict) or set(actual) != EXPECTED_KEYS:
            raise AssertionError(f"example {index} returned the wrong schema")
        compare(actual, example["expected"], atol=atol, rtol=rtol,
                path=f"example[{index}]")
        print(f"PASS {index}/5 {example['name']}")
    print("All 5 locked-DockQ public examples passed.")


if __name__ == "__main__":
    main()
