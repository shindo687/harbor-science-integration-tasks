#!/usr/bin/env python3
"""Add a forbidden donor import for source-gate calibration."""

from pathlib import Path


path = Path(
    "/testbed/sklearn/ensemble/_second_order_gradient_boosting.py"
)
text = path.read_text(encoding="utf-8")
needle = "from __future__ import annotations\n"
if text.count(needle) != 1:
    raise RuntimeError("future import not found exactly once")
path.write_text(
    text.replace(needle, needle + "import xgboost\n", 1), encoding="utf-8"
)
