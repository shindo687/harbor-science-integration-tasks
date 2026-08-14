#!/usr/bin/env python3
"""Immutable JSON adapter for the submitted OpenMM analysis module."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


MODULE = Path("/testbed/wrappers/python/openmm/app/vina_score.py")
REQUIRED = (
    "affinity", "raw_interaction", "torsional_penalty", "torsional_divisor",
    "terms", "pairs", "receptor_forces", "ligand_forces",
)


def load_function():
    spec = importlib.util.spec_from_file_location("openmm_vina_score", MODULE)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load vina_score module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.score_vina_pose


def encode(result):
    if not isinstance(result, dict):
        raise TypeError("score_vina_pose must return a dict")
    missing = [key for key in REQUIRED if key not in result]
    if missing:
        raise KeyError(f"missing result keys: {missing}")
    if set(result) != set(REQUIRED):
        raise KeyError("score_vina_pose returned unexpected keys")
    # A JSON round trip enforces serializable finite values in the grader.
    return {key: result[key] for key in REQUIRED}


def run_one(function, case):
    try:
        result = function(
            case["receptor"]["types"], case["receptor"]["positions"],
            case["ligand"]["types"], case["ligand"]["positions"],
            case["num_rotatable_bonds"], cutoff=case["cutoff"],
        )
        return {"name": case.get("name"), "result": encode(result)}
    except Exception as exc:
        return {"name": case.get("name"), "error": type(exc).__name__}


def main():
    request = json.load(sys.stdin)
    function = load_function()
    json.dump(
        {"cases": [run_one(function, case) for case in request["cases"]]},
        sys.stdout, allow_nan=False, separators=(",", ":"),
    )


if __name__ == "__main__":
    main()
