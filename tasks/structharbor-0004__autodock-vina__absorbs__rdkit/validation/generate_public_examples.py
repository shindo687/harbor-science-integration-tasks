#!/usr/bin/env python3
"""Generate disclosed packets from the locked official RDKit reference."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import cases  # noqa: E402
import reference_runner  # noqa: E402


def main():
    destination = ROOT / "environment" / "public-examples"
    for old in destination.glob("[0-9][0-9]-*.json"):
        old.unlink()
    for number, description in enumerate(cases.public_cases(), 1):
        row = reference_runner.run_one(description)
        payload = {
            "input": {"name": row["name"], "packet": row["packet"]},
            "expected": row["result"],
        }
        path = destination / f"{number:02d}-{description['name']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
