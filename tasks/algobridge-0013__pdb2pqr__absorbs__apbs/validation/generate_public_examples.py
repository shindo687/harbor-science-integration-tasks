#!/usr/bin/env python3
"""Generate the five disclosed packets from the locked official APBS runtime."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import public_cases  # noqa: E402
from reference_runner import run  # noqa: E402


def main():
    output = ROOT / "environment" / "public-examples"
    output.mkdir(parents=True, exist_ok=True)
    for old in output.glob("[0-9][0-9]-*.json"):
        old.unlink()
    for index, description in enumerate(public_cases(), 1):
        row = run(description)
        payload = {
            "input": {"name": row["name"], "packet": row["packet"]},
            "expected": row["expected"],
        }
        path = output / f"{index:02d}-{row['name']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
