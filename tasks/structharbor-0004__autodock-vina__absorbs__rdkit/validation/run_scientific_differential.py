#!/usr/bin/env python3
"""Compare the clean-room solution with native RDKit outside Harbor."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import cases  # noqa: E402
import reference_runner  # noqa: E402


def main():
    spec = importlib.util.spec_from_file_location("oracle_mmff94", ROOT / "solution/mmff94.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    maximum = 0.0
    for description in cases.public_cases() + cases.hidden_cases():
        row = reference_runner.run_one(description)
        observed = module.score_mmff94(row["packet"])
        delta = max(abs(observed[name] - row["result"][name]) for name in observed)
        maximum = max(maximum, delta)
        print(f"{description['name']}: max_abs={delta:.12g}")
    print(f"overall_max_abs={maximum:.12g}")
    if maximum > 1e-7:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
