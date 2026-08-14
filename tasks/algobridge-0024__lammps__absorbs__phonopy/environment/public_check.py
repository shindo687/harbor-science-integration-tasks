#!/usr/bin/env python3
"""Replay public fixtures without installing the private reference runtime."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile


EXAMPLES = Path("/public-examples")
EXECUTABLE = Path("/testbed/src/lmp_serial")


def flatten(value):
    if isinstance(value, list):
        for item in value:
            yield from flatten(item)
    else:
        yield float(value)


def close(actual, expected, *, atol, rtol):
    actual_values = list(flatten(actual))
    expected_values = list(flatten(expected))
    return len(actual_values) == len(expected_values) and all(
        math.isfinite(a) and math.isclose(a, b, abs_tol=atol, rel_tol=rtol)
        for a, b in zip(actual_values, expected_values, strict=True)
    )


def check(payload, work):
    input_path = work / "input.json"
    output_path = work / "output.json"
    script_path = work / "run.in"
    input_path.write_text(json.dumps(payload["input"]) + "\n", encoding="utf-8")
    script_path.write_text(f"fit_harmonic_fc2 {input_path} {output_path}\n", encoding="utf-8")
    process = subprocess.run(
        [str(EXECUTABLE), "-log", "none", "-screen", "none", "-in", str(script_path)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=120,
        check=False,
    )
    if process.returncode != 0 or not output_path.is_file():
        return False, process.stdout[-1000:]
    actual = json.loads(output_path.read_text(encoding="utf-8"))
    expected = payload["expected"]
    if actual.get("format") != expected.get("format"):
        return False, "wrong output format"
    checks = [
        close(actual["force_constants"], expected["force_constants"], atol=2e-8, rtol=2e-8),
        math.isclose(actual["fit_residual_rms"], expected["fit_residual_rms"], abs_tol=2e-10, rel_tol=2e-7),
    ]
    if len(actual.get("qpoint_results", [])) != len(expected["qpoint_results"]):
        return False, "wrong q-point result count"
    for got, ref in zip(actual["qpoint_results"], expected["qpoint_results"], strict=True):
        checks.extend(
            (
                close(got["dynamical_matrix_real"], ref["dynamical_matrix_real"], atol=2e-8, rtol=2e-8),
                close(got["dynamical_matrix_imag"], ref["dynamical_matrix_imag"], atol=2e-8, rtol=2e-8),
                close(got["eigenvalues"], ref["eigenvalues"], atol=2e-8, rtol=2e-8),
                close(got["frequencies"], ref["frequencies"], atol=1e-6, rtol=2e-7),
            )
        )
    return all(checks), "" if all(checks) else "numerical mismatch"


def main():
    if not EXECUTABLE.is_file():
        print("missing /testbed/src/lmp_serial; run: make -C /testbed/src serial -j8", file=sys.stderr)
        return 2
    passed = 0
    fixtures = sorted(EXAMPLES.glob("*.json"))
    with tempfile.TemporaryDirectory(prefix="fc2-public-") as temp:
        root = Path(temp)
        for fixture in fixtures:
            case_root = root / fixture.stem
            case_root.mkdir()
            ok, detail = check(json.loads(fixture.read_text(encoding="utf-8")), case_root)
            passed += int(ok)
            print(f"{'PASS' if ok else 'FAIL'} {fixture.name}{': ' + detail if detail else ''}")
    print(f"public examples: {passed}/{len(fixtures)}")
    return 0 if passed == len(fixtures) else 1


if __name__ == "__main__":
    raise SystemExit(main())

