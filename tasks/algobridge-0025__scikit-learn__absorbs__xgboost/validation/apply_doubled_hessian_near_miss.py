#!/usr/bin/env python3
"""Apply a plausible curvature-convention error to the clean Oracle."""

from pathlib import Path


path = Path(
    "/testbed/sklearn/ensemble/_second_order_gradient_boosting.py"
)
text = path.read_text(encoding="utf-8")
needle = "        return gradient, hessian\n"
replacement = (
    "        # Near miss: an erroneous loss convention doubles curvature.\n"
    "        hessian = np.asarray(np.float32(2.0) * hessian, dtype=np.float32)\n"
    "        return gradient, hessian\n"
)
if text.count(needle) != 1:
    raise RuntimeError("Oracle gradient return point not found exactly once")
path.write_text(text.replace(needle, replacement), encoding="utf-8")
