#!/bin/sh
set -eu
target=/testbed/sklearn/ensemble
cp /solution/_second_order_gradient_boosting.py \
  "$target/_second_order_gradient_boosting.py"
python - <<'PY'
from pathlib import Path

path = Path("/testbed/sklearn/ensemble/__init__.py")
text = path.read_text(encoding="utf-8")
statement = (
    "from sklearn.ensemble._second_order_gradient_boosting import "
    "SecondOrderGradientBoosting\n"
)
if statement not in text:
    text = statement + text
if '"SecondOrderGradientBoosting"' not in text:
    marker = "__all__ = [\n"
    if marker not in text:
        raise RuntimeError("could not locate sklearn.ensemble.__all__")
    text = text.replace(marker, marker + '    "SecondOrderGradientBoosting",\n', 1)
path.write_text(text, encoding="utf-8")
PY
