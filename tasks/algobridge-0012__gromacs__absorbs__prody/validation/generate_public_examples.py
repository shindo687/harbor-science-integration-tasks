#!/usr/bin/env python3
"""Generate five public ANM fixtures through the locked reference pipeline."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np


sys.path.insert(0, "/repo/tests")
from cases import item  # noqa: E402
from reference_runner import jsonify, run_one  # noqa: E402


OUTPUT = Path("/output")


def public_cases():
    irregular = np.array([
        [0.00, 0.00, 0.00], [0.47, 0.03, 0.06],
        [0.13, 0.56, 0.12], [0.07, 0.19, 0.69],
        [0.62, 0.51, 0.41],
    ])
    angle = 0.93 * np.arange(7)
    helix = np.column_stack([
        0.39 * np.cos(angle), 0.39 * np.sin(angle), 0.24 * np.arange(7)
    ])
    disconnected = np.vstack([
        irregular,
        irregular + np.array([3.2, -0.4, 0.2]),
    ])
    full = np.vstack([
        irregular,
        [[1.9, 1.7, -0.3], [-0.8, 0.6, 1.5]],
    ])
    planar = np.array([
        [0.38 * x, 0.38 * y, 0.0]
        for y in range(2)
        for x in range(4)
    ])
    return [
        item("public_irregular_five", irregular,
             cutoff_nm=1.0, gamma=1.2, n_modes=6),
        item("public_helical_seven", helix,
             cutoff_nm=0.79, gamma=0.8, n_modes=8),
        item("public_disconnected_components", disconnected,
             cutoff_nm=1.0, gamma=1.0, n_modes=18),
        item("public_ordered_selection", full,
             selection=[4, 1, 3, 0], cutoff_nm=1.0, n_modes=6),
        item("public_planar_gamma", planar,
             cutoff_nm=0.55, gamma=2.4, n_modes=16),
    ]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT.glob("[0-9][0-9]-*.json"):
        old.unlink()
    for index, case in enumerate(public_cases(), start=1):
        expected = jsonify(run_one(case))
        path = OUTPUT / f"{index:02d}-{case['name']}.json"
        path.write_text(
            json.dumps({"input": case, "expected": expected}, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
