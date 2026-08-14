#!/usr/bin/env python3
"""Run the submitted module against the five disclosed examples."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path


MODULE = Path("/testbed/wrappers/python/openmm/app/vina_score.py")
EXAMPLES = Path("/examples")


def load_function():
    spec = importlib.util.spec_from_file_location("openmm_vina_score", MODULE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.score_vina_pose


def maximum_delta(first, second):
    if isinstance(first, dict) and isinstance(second, dict) and set(first) == set(second):
        return max((maximum_delta(first[key], second[key]) for key in first), default=0.0)
    if isinstance(first, list) and isinstance(second, list) and len(first) == len(second):
        return max((maximum_delta(a, b) for a, b in zip(first, second)), default=0.0)
    if (isinstance(first, (int, float)) and not isinstance(first, bool)
            and isinstance(second, (int, float)) and not isinstance(second, bool)):
        return abs(float(first) - float(second))
    return 0.0 if first == second else math.inf


def main():
    function = load_function()
    failures = 0
    for path in sorted(EXAMPLES.glob("[0-9][0-9]-*.json")):
        example = json.loads(path.read_text())
        case = example["input"]
        result = function(
            case["receptor"]["types"], case["receptor"]["positions"],
            case["ligand"]["types"], case["ligand"]["positions"],
            case["num_rotatable_bonds"], cutoff=case["cutoff"],
        )
        delta = maximum_delta(example["expected"], result)
        passed = delta <= 2e-6
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'} {case['name']} max_abs={delta:.3g}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
