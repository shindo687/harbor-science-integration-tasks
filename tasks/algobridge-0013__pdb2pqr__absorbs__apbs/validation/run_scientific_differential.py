#!/usr/bin/env python3
"""Local all-case official-APBS versus clean-room differential check."""

from __future__ import annotations

import math
from pathlib import Path
import sys

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "solution"))

from cases import hidden_cases, public_cases  # noqa: E402
from reference_runner import run  # noqa: E402
from lpbe_grid import solve_lpbe  # noqa: E402


def main():
    failures = 0
    for description in public_cases() + hidden_cases():
        reference = run(description)
        observed = solve_lpbe(reference["packet"])
        potential_error = float(np.max(np.abs(
            np.asarray(observed["potential"]) - np.asarray(reference["expected"]["potential"])
        )))
        energy_error = abs(observed["energy_kj_mol"] - reference["expected"]["energy_kj_mol"])
        energy_limit = max(0.02, 2e-4 * max(1.0, abs(reference["expected"]["energy_kj_mol"])))
        residual = observed["diagnostics"]["relative_residual"]
        passed = (math.isfinite(potential_error) and potential_error <= 1e-4
                  and energy_error <= energy_limit and residual <= 2e-9)
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'} {reference['name']} "
              f"potential_max_abs={potential_error:.6g} energy_abs={energy_error:.6g} "
              f"relative_residual={residual:.3g}")
    if failures:
        raise SystemExit(f"{failures} differential case(s) failed")


if __name__ == "__main__":
    main()
