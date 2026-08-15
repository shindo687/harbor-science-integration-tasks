#!/usr/bin/env python3
"""Run the submitted LPBE kernel against five disclosed APBS examples."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np


MODULE = Path("/testbed/pdb2pqr/lpbe_grid.py")


def main():
    spec = importlib.util.spec_from_file_location("pdb2pqr_lpbe_grid", MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load submitted module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failures = 0
    for path in sorted(Path("/examples").glob("[0-9][0-9]-*.json")):
        example = json.loads(path.read_text())
        packet, expected = example["input"]["packet"], example["expected"]
        try:
            result = module.solve_lpbe(packet)
            potential_error = float(np.max(np.abs(
                np.asarray(result["potential"]) - np.asarray(expected["potential"])
            )))
            energy_error = abs(float(result["energy_kj_mol"]) - float(expected["energy_kj_mol"]))
            energy_limit = max(0.02, 2e-4 * max(1.0, abs(float(expected["energy_kj_mol"]))))
            residual = float(result["diagnostics"]["relative_residual"])
            passed = (math.isfinite(potential_error) and potential_error <= 1e-4
                      and math.isfinite(energy_error) and energy_error <= energy_limit
                      and math.isfinite(residual) and residual <= 2e-9)
        except Exception as error:
            potential_error = energy_error = residual = math.inf
            passed = False
            print(f"ERROR {example['input']['name']} {type(error).__name__}: {error}")
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'} {example['input']['name']} "
              f"potential_max_abs={potential_error:.3g} energy_abs={energy_error:.3g} "
              f"relative_residual={residual:.3g}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
