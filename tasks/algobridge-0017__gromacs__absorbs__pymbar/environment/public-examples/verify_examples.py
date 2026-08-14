#!/usr/bin/env python3
"""Build-independent checker for the five visible BAR fixtures."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


GROMACS = Path(os.environ["CANDIDATE_GMX"])
ROOT = Path(__file__).resolve().parent
KEYS = {
    "delta_f", "uncertainty", "overlap", "iterations",
    "function_evaluations", "residual", "converged", "n_forward",
    "n_reverse",
}


def serialize(spec):
    return "\n".join([
        "BAR_INTERNAL_V1",
        f"relative_tolerance {spec['relative_tolerance']:.17g}",
        f"maximum_iterations {spec['maximum_iterations']}",
        f"initial_delta_f {spec['initial_delta_f']:.17g}",
        f"forward {len(spec['forward'])}",
        " ".join(f"{value:.17g}" for value in spec["forward"]),
        f"reverse {len(spec['reverse'])}",
        " ".join(f"{value:.17g}" for value in spec["reverse"]),
        "",
    ])


def main():
    fixtures = sorted(ROOT.glob("[0-9][0-9]-*.json"))
    if len(fixtures) != 5:
        raise SystemExit(f"expected five public fixtures, found {len(fixtures)}")
    with tempfile.TemporaryDirectory(prefix="algobridge0017-public-") as directory:
        work = Path(directory)
        for fixture_path in fixtures:
            fixture = json.loads(fixture_path.read_text())
            source = work / (fixture_path.stem + ".bar")
            output = work / (fixture_path.stem + ".out.json")
            source.write_text(serialize(fixture["input"]))
            completed = subprocess.run(
                [str(GROMACS), "bar-internal", "-f", str(source), "-o", str(output)],
                text=True, capture_output=True, timeout=120, check=False,
                env={
                    "PATH": "/usr/bin:/bin", "HOME": str(work),
                    "GMX_MAXBACKUP": "-1", "GMX_NO_QUOTES": "1",
                    "OMP_NUM_THREADS": "1",
                },
            )
            if completed.returncode != 0 or not output.is_file():
                raise SystemExit(
                    f"FAIL {fixture_path.name}: command returned {completed.returncode}\n"
                    f"{completed.stderr[-1000:]}"
                )
            observed = json.loads(output.read_text())
            if set(observed) != KEYS or observed.get("converged") is not True:
                raise SystemExit(f"FAIL {fixture_path.name}: JSON protocol")
            expected = fixture["expected"]
            checks = (
                abs(float(observed["delta_f"]) - expected["delta_f"]) <= 1e-9,
                abs(float(observed["uncertainty"]) - expected["uncertainty"]) <= 1e-7,
                abs(float(observed["overlap"]) - expected["overlap"]) <= 2e-8,
                math.isfinite(float(observed["residual"])),
                float(observed["residual"]) <= 1e-10,
                observed["n_forward"] == len(fixture["input"]["forward"]),
                observed["n_reverse"] == len(fixture["input"]["reverse"]),
            )
            if not all(checks):
                raise SystemExit(
                    f"FAIL {fixture_path.name}: expected={expected} observed={observed}"
                )
            print(f"PASS {fixture_path.name}")
    print("Public examples: 5/5")


if __name__ == "__main__":
    main()
