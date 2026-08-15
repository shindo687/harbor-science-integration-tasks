#!/usr/bin/env python3
"""Run clean-room ETKDG output against native RDKit metrics."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import cases  # noqa: E402
import grader  # noqa: E402
import reference_runner  # noqa: E402


def main():
    spec = importlib.util.spec_from_file_location("oracle_etkdg", ROOT / "solution/etkdg_init.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failed = 0
    for description in cases.public_cases() + cases.hidden_cases():
        row = reference_runner.run_one(description)
        result = module.embed_etkdg(row["packet"])
        passed, reasons, metrics = grader.compare_case(row["packet"], row["result"], result)
        failed += not passed
        print(f"{'PASS' if passed else 'FAIL'} {row['name']} {reasons} {metrics}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
