#!/usr/bin/env python3
"""Regenerate the five visible cases with the locked donor reference."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import public_cases  # noqa: E402
from reference_runner import calculate  # noqa: E402


def main():
    destination = ROOT / "public-examples"
    destination.mkdir(parents=True, exist_ok=True)
    for index, case in enumerate(public_cases(), 1):
        stem = f"{index:02d}-{case['name']}"
        (destination / f"{stem}.input.json").write_text(
            json.dumps(case, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
        (destination / f"{stem}.expected.json").write_text(
            json.dumps(calculate(case), indent=2, sort_keys=True, allow_nan=False)
            + "\n"
        )
    entries = []
    for path in sorted(destination.glob("*.json")):
        entries.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (destination / "SHA256SUMS").write_text("\n".join(entries) + "\n")


if __name__ == "__main__":
    main()
