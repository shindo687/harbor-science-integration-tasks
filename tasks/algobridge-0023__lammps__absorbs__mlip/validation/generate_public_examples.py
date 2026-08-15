#!/usr/bin/env python3
"""Regenerate disclosed packets with the locked official MLIP-3 oracle."""

from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import PUBLIC_CASES  # noqa: E402
from reference_runner import run_reference  # noqa: E402


def main():
    output = ROOT / "environment" / "public-examples"
    output.mkdir(parents=True, exist_ok=True)
    for index, packet in enumerate(PUBLIC_CASES, 1):
        payload = {"case": packet, "expected": run_reference(packet)}
        path = output / f"{index:02d}-{packet['name'].removeprefix('public_')}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

