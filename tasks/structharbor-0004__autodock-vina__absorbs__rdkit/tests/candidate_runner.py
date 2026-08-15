#!/usr/bin/env python3
"""Immutable JSON adapter for the submitted Vina MMFF94 module."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


MODULE = Path("/testbed/build/python/vina/mmff94.py")
REQUIRED = (
    "bond", "angle", "stretch_bend", "out_of_plane", "torsion",
    "van_der_waals", "electrostatic", "total",
)


def load_function():
    spec = importlib.util.spec_from_file_location("vina_mmff94", MODULE)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load mmff94 module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.score_mmff94


def run_one(function, case):
    try:
        result = function(case["packet"])
        if not isinstance(result, dict) or set(result) != set(REQUIRED):
            raise TypeError("score_mmff94 returned an invalid result schema")
        return {"name": case.get("name"), "result": result}
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
