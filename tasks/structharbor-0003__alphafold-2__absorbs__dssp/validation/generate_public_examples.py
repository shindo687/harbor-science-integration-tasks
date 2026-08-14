#!/usr/bin/env python3
"""Regenerate the five public fixtures with the locked native reference."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

import reference_runner  # noqa: E402
from cases import public_cases  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prefix", default="/opt/dssp")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "environment/public-examples")
    args = parser.parse_args()
    prefix = Path(args.prefix)
    reference_runner.MKDSSP = str(prefix / "bin/mkdssp")
    reference_runner.DATA_DIR = str(prefix / "share/libcifpp")
    reference_runner.DICTIONARY = str(prefix / "share/libcifpp/mmcif_pdbx.dic")
    args.output.mkdir(parents=True, exist_ok=True)
    for old in args.output.glob("[0-9][0-9]-*.json"):
        old.unlink()
    for index, case in enumerate(public_cases(), 1):
        payload = {
            "case": case,
            "expected": reference_runner.run_one(case),
            "reference": "native mkdssp 4.4.11",
        }
        target = args.output / f"{index:02d}-{case['name']}.json"
        target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        print(target)


if __name__ == "__main__":
    main()

