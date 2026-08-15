#!/usr/bin/env python3
"""Regenerate disclosed packets and locked CCMpred outputs."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import reference_runner  # noqa: E402
from cases import PUBLIC_CASES  # noqa: E402


def main() -> None:
    reference_runner.REFERENCE = Path(
        "/tmp/algobridge-0008-upstream.m435Cw/ccmpred/build/bin/ccmpred"
    )
    destination = ROOT / "environment" / "public-examples"
    destination.mkdir(parents=True, exist_ok=True)
    for index, packet in enumerate(PUBLIC_CASES, 1):
        expected = reference_runner.run_reference(packet)
        path = destination / f"{index:02d}-{packet['name']}.json"
        path.write_text(
            json.dumps({"packet": packet, "expected": expected}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
