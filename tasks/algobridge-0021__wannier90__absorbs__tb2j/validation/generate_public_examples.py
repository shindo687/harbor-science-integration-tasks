#!/usr/bin/env python3
"""Regenerate published inputs and expected outputs with locked real TB2J."""

from __future__ import annotations

import json
import hashlib
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import public_cases, write_case  # noqa: E402
from reference_runner import run_reference  # noqa: E402


def main() -> int:
    destinations = [
        ROOT / "public-examples",
        ROOT / "environment" / "public-examples",
        ROOT / "tests" / "public-examples",
    ]
    for destination in destinations:
        destination.mkdir(parents=True, exist_ok=True)

    primary = destinations[0]
    for index, case in enumerate(public_cases(), start=1):
        stem = f"{index:02d}-{case['name']}"
        input_path = primary / f"{stem}.input.json"
        expected_path = primary / f"{stem}.expected.json"
        write_case(input_path, case)
        result = run_reference(input_path)
        if result.get("status") != "ok":
            raise RuntimeError(f"reference failed for {case['name']}: {result}")
        expected_path.write_text(
            json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
        )
        for destination in destinations[1:]:
            shutil.copy2(input_path, destination / input_path.name)
            shutil.copy2(expected_path, destination / expected_path.name)

    for destination in destinations:
        rows = []
        for path in sorted(destination.glob("*.json")):
            rows.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
        (destination / "SHA256SUMS").write_text("\n".join(rows) + "\n")

    print(f"generated {len(public_cases())} locked public input/expected pairs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
