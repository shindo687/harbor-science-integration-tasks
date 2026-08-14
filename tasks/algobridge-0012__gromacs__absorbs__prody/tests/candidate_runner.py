#!/usr/bin/env python3
"""Run the submitted gmxapi ANM module through a bounded JSON protocol."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import numpy as np


MODULE = Path(
    "/testbed/python_packaging/gmxapi/src/gmxapi/analysis/anm.py"
)


def load_api():
    specification = importlib.util.spec_from_file_location(
        "gmxapi_analysis_anm_candidate", MODULE
    )
    if specification is None or specification.loader is None:
        raise ImportError("could not load candidate ANM module")
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module.analyze_anm


def jsonify(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonify(item) for item in value]
    return value


def main():
    analyze_anm = load_api()
    request = json.load(sys.stdin)
    output = []
    for case in request["cases"]:
        try:
            result = analyze_anm(
                np.asarray(case["coordinates_nm"], dtype=float),
                **case["arguments"],
            )
            output.append({"name": case["name"], "result": jsonify(result)})
        except Exception as exc:
            output.append({
                "name": case["name"],
                "error": type(exc).__name__,
                "message": str(exc),
            })
    json.dump({"cases": output}, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
