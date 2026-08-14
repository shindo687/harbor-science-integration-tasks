#!/usr/bin/env python3
"""Regenerate public examples with the locked real mkdssp adapter."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import public_cases  # noqa: E402
from reference_runner import run_one  # noqa: E402


def main():
    destinations = [ROOT / "public-examples", ROOT / "environment/public-examples"]
    for destination in destinations:
        destination.mkdir(parents=True, exist_ok=True)
        for old in destination.glob("[0-9][0-9]-*.json"):
            old.unlink()
    for number, case in enumerate(public_cases(), 1):
        document = {"case": case, "expected": run_one(case)}
        name = f"{number:02d}-{case['name'].removeprefix('public_').replace('_', '-')}.json"
        text = json.dumps(document, indent=2, sort_keys=True, allow_nan=False) + "\n"
        for destination in destinations:
            (destination / name).write_text(text)


if __name__ == "__main__":
    main()
