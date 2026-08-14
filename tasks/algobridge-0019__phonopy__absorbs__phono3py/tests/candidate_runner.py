#!/usr/bin/env python3
"""Run the submitted phonopy FC3 API through a bounded JSON protocol."""

from __future__ import annotations

import json
import sys

import numpy as np
from phonopy.harmonic.third_order import fit_fc3
from phonopy.structure.atoms import PhonopyAtoms


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


def make_cell(specification):
    return PhonopyAtoms(
        symbols=specification["symbols"],
        cell=specification["cell"],
        scaled_positions=specification["scaled_positions"],
    )


def run_one(item):
    return fit_fc3(
        make_cell(item["cell"]),
        np.asarray(item["displacements"], dtype=float),
        np.asarray(item["forces"], dtype=float),
        **item["arguments"],
    )


def main():
    payload = json.load(sys.stdin)
    output = []
    for item in payload["cases"]:
        try:
            output.append({"name": item["name"], "result": jsonify(run_one(item))})
        except Exception as exc:
            output.append({
                "name": item["name"],
                "error": type(exc).__name__,
                "message": str(exc),
            })
    json.dump({"cases": output}, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
