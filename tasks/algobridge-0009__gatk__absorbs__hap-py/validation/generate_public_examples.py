#!/usr/bin/env python3
"""Regenerate disclosed packets and native hap.py expected results."""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import public_cases  # noqa: E402
from reference_runner import compare  # noqa: E402


def main():
    if "HAPPY_REFERENCE_BIN" not in os.environ:
        raise SystemExit("set HAPPY_REFERENCE_BIN to the locked hap.py build bin directory")
    destination = ROOT / "environment" / "public-examples"
    destination.mkdir(parents=True, exist_ok=True)
    for index, packet in enumerate(public_cases(), 1):
        value = {"packet": packet, "expected": compare(packet)}
        path = destination / f"{index:02d}-{packet['name']}.json"
        path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
        print(path)


if __name__ == "__main__":
    main()
