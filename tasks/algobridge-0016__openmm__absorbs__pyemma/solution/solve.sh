#!/bin/sh
set -eu

cp /solution/markov_model.py /testbed/wrappers/python/openmm/app/markov_model.py
python - <<'PY'
from pathlib import Path

path = Path("/testbed/wrappers/python/openmm/app/__init__.py")
text = path.read_text(encoding="utf-8")
line = "from .markov_model import estimate_markov_model\n"
if line not in text:
    text += "\n" + line
path.write_text(text, encoding="utf-8")
PY

