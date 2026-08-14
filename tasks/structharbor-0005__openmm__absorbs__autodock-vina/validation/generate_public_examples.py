#!/usr/bin/env python3
"""Generate disclosed examples from the locked native Vina reference."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import cases  # noqa: E402
import reference_runner  # noqa: E402


def main():
    reference_runner.REFERENCE = str(ROOT / "tests" / "vina-potential-reference")
    destination = ROOT / "environment" / "public-examples"
    for number, case in enumerate(cases.public_cases(), 1):
        payload = {"input": case, "expected": reference_runner.run_one(case)}
        path = destination / f"{number:02d}-{case['name']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
