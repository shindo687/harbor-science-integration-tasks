#!/usr/bin/env python3
"""Immutable adapter for the submitted CREST ETKDG module."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


MODULE = Path("/testbed/src/etkdg_init.py")
REQUIRED = ("conformers", "failures", "rmsd_matrix", "bounds", "diagnostics")


def load_function():
    spec = importlib.util.spec_from_file_location("crest_etkdg", MODULE)
    if spec is None or spec.loader is None:
        raise ImportError("cannot load etkdg_init module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.embed_etkdg


def run_one(function, case):
    try:
        result = function(case["packet"])
        if not isinstance(result, dict) or set(result) != set(REQUIRED):
            raise TypeError("embed_etkdg returned an invalid result schema")
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
