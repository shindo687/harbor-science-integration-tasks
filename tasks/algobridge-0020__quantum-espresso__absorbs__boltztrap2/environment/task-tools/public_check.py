#!/usr/bin/env python3
"""Run the candidate against the five visible examples without donor code."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys

from candidate_runner import CandidateProgram


CASES = Path("/public-cases")
TOLERANCES = {
    "electron_count": (2e-8, 2e-11),
    "carrier_density_cm3": (2e-8, 1e9),
    "L0": (2e-8, 1e-14),
    "L1": (2e-8, 1e-16),
    "L2": (2e-8, 1e-18),
    "sigma_over_tau_S_m_s": (2e-8, 1e5),
    "seebeck_V_K": (1e-6, 1e-10),
    "kappa_over_tau_W_m_K_s": (1e-6, 100.0),
}


def numbers(value):
    if isinstance(value, list):
        for item in value:
            yield from numbers(item)
    else:
        yield float(value)


def close(expected, actual, rtol, atol):
    left = list(numbers(expected))
    right = list(numbers(actual))
    if len(left) != len(right):
        return False
    return all(
        math.isfinite(b) and abs(a - b) <= atol + rtol * abs(a)
        for a, b in zip(left, right)
    )


def main():
    program = CandidateProgram("/testbed", "/opt/task-tools/transport_driver.f90")
    passed = 0
    try:
        for input_path in sorted(CASES.glob("*.input.json")):
            expected_path = Path(str(input_path).replace(".input.json", ".expected.json"))
            payload = json.loads(input_path.read_text())
            expected = json.loads(expected_path.read_text())
            try:
                output = program.run(payload)
                failed_keys = [
                    key for key, tolerance in TOLERANCES.items()
                    if not close(expected[key], output[key], *tolerance)
                ]
                ok = not failed_keys
            except Exception as exc:
                ok = False
                print(f"FAIL {payload['name']}: {exc}")
            else:
                suffix = "" if ok else ": " + ", ".join(failed_keys)
                print(("PASS " if ok else "FAIL ") + payload["name"] + suffix)
            passed += int(ok)
    finally:
        program.close()
    print(f"public examples: {passed}/5")
    return 0 if passed == 5 else 1


if __name__ == "__main__":
    raise SystemExit(main())
