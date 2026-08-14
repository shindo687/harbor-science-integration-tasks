#!/usr/bin/env python3
"""Locked pristine GROMACS -> pristine pymbar BAR reference runner."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile

os.environ["PYMBAR_DISABLE_JAX"] = "1"

import numpy as np
from pymbar import bar, bar_overlap


GROMACS = Path(os.environ.get(
    "REFERENCE_GMX", "/opt/reference-gromacs-build/bin/gmx"
))


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command, *, timeout=120):
    environment = {
        **os.environ,
        "GMX_MAXBACKUP": "-1",
        "GMX_NO_QUOTES": "1",
        "OMP_NUM_THREADS": "1",
    }
    completed = subprocess.run(
        command,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        env=environment,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"GROMACS failed ({completed.returncode}): {completed.stderr[-2000:]}"
        )
    return completed


def _gromacs_roundtrip(values, root, stem):
    source = root / f"{stem}-source.xvg"
    output = root / f"{stem}-gromacs.xvg"
    lines = ["# locked reduced-work series", "@ xaxis label \"sample\""]
    lines.extend(f"{index:d} {float(value):.17g}" for index, value in enumerate(values))
    source.write_text("\n".join(lines) + "\n")
    completed = _run([
        str(GROMACS), "analyze", "-f", str(source), "-av", str(output),
        "-xvg", "none",
    ])
    parsed = []
    for line in output.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in "#@&":
            continue
        fields = stripped.split()
        if len(fields) != 2:
            raise RuntimeError(f"unexpected GROMACS XVG row: {line!r}")
        parsed.append(float(fields[1]))
    expected = np.asarray(values, dtype=float)
    observed = np.asarray(parsed, dtype=float)
    if observed.shape != expected.shape or not np.allclose(
            observed, expected, atol=2.0e-6, rtol=2.0e-7):
        raise RuntimeError("GROMACS reduced-work XVG roundtrip mismatch")
    return observed, {
        "source_sha256": _sha256(source),
        "output_sha256": _sha256(output),
        "count": len(parsed),
        "stdout_tail": completed.stdout[-500:],
    }


def _log_fermi(argument):
    return -np.logaddexp(0.0, argument)


def _residual(forward, reverse, delta):
    count_offset = math.log(len(forward) / len(reverse))
    forward_logs = _log_fermi(count_offset + forward - delta)
    reverse_logs = _log_fermi(-count_offset + reverse + delta)
    return abs(float(np.logaddexp.reduce(forward_logs)
                     - np.logaddexp.reduce(reverse_logs)))


def solve_case(spec, root):
    case_root = root / spec["name"]
    case_root.mkdir()
    forward, forward_trace = _gromacs_roundtrip(
        spec["forward"], case_root, "forward"
    )
    reverse, reverse_trace = _gromacs_roundtrip(
        spec["reverse"], case_root, "reverse"
    )
    result = bar(
        forward,
        reverse,
        DeltaF=float(spec["initial_delta_f"]),
        compute_uncertainty=True,
        uncertainty_method="BAR",
        maximum_iterations=int(spec["maximum_iterations"]),
        relative_tolerance=float(spec["relative_tolerance"]),
        method="false-position",
        iterated_solution=True,
        verbose=False,
    )
    delta = float(result["Delta_f"])
    canonical = {
        "name": spec["name"],
        "forward": forward.tolist(),
        "reverse": reverse.tolist(),
        "initial_delta_f": float(spec["initial_delta_f"]),
        "relative_tolerance": float(spec["relative_tolerance"]),
        "maximum_iterations": int(spec["maximum_iterations"]),
    }
    return {
        "name": spec["name"],
        "input": canonical,
        "expected": {
            "delta_f": delta,
            "uncertainty": float(result["dDelta_f"]),
            "overlap": float(bar_overlap(forward, reverse)),
            "residual": _residual(forward, reverse, delta),
            "n_forward": len(forward),
            "n_reverse": len(reverse),
        },
        "gromacs_trace": {
            "forward": forward_trace,
            "reverse": reverse_trace,
        },
    }


def main():
    request = json.load(sys.stdin)
    if not GROMACS.is_file():
        raise SystemExit(f"locked GROMACS binary is missing: {GROMACS}")
    version = _run([str(GROMACS), "--version"]).stdout
    with tempfile.TemporaryDirectory(prefix="algobridge0017-reference-") as directory:
        root = Path(directory)
        response = {
            "gromacs_version": next(
                (line.strip() for line in version.splitlines()
                 if "GROMACS version:" in line),
                "unknown",
            ),
            "cases": [solve_case(case, root) for case in request["cases"]],
        }
    json.dump(response, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()

