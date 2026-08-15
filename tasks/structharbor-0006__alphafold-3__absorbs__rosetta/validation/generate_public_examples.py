#!/usr/bin/env python3
"""Generate the public JSON packets from the canonical fixture definitions."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from cases import public_cases  # noqa: E402


def main() -> None:
    output = ROOT / "environment" / "public-examples"
    output.mkdir(parents=True, exist_ok=True)
    for index, packet in enumerate(public_cases(), 1):
        path = output / f"{index:02d}-{packet['name']}.json"
        path.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
        print(path)


if __name__ == "__main__":
    main()
