#!/usr/bin/env python3
"""Build the submitted pair style and run the five disclosed MLIP comparisons."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

from candidate_runner import run_candidate


def close(left, right, absolute, relative):
    return abs(left - right) <= absolute + relative * max(abs(left), abs(right))


def compare(expected, observed):
    return (
        close(expected["energy"], observed["energy"], 2.0e-9, 2.0e-10)
        and all(close(a, b, 2.0e-5, 2.0e-6)
                for row_a, row_b in zip(expected["forces"], observed["forces"])
                for a, b in zip(row_a, row_b))
        and all(close(a, b, 3.0e-4, 3.0e-6)
                for a, b in zip(expected["virial"], observed["virial"]))
    )


def main():
    required = (Path("/testbed/src/pair_mtp_bounded.cpp"),
                Path("/testbed/src/pair_mtp_bounded.h"))
    if any(not path.is_file() for path in required):
        print("missing the two required pair_mtp_bounded source files", file=sys.stderr)
        return 2
    built = subprocess.run(
        ["make", "-C", "/testbed/src", "serial", "-j8"],
        text=True, capture_output=True, timeout=900, check=False,
    )
    if built.returncode:
        print(built.stderr[-3000:], file=sys.stderr)
        return 2
    passed = 0
    examples = sorted(Path("/examples").glob("*.json"))
    for path in examples:
        payload = json.loads(path.read_text(encoding="utf-8"))
        try:
            observed = run_candidate(payload["case"])
            ok = compare(payload["expected"], observed)
        except Exception as error:
            ok = False
            print(f"{path.stem}: ERROR {type(error).__name__}: {error}")
        else:
            print(f"{path.stem}: {'PASS' if ok else 'FAIL'}")
        passed += int(ok)
    print(f"public examples: {passed}/{len(examples)}")
    return 0 if examples and passed == len(examples) else 1


if __name__ == "__main__":
    raise SystemExit(main())

