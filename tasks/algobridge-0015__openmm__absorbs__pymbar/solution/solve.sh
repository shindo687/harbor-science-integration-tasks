#!/bin/sh
set -eu

cp /solution/mbar.py /testbed/wrappers/python/openmm/app/mbar.py
python - <<'PY'
from pathlib import Path

path = Path("/testbed/wrappers/python/openmm/app/__init__.py")
text = path.read_text(encoding="utf-8")
line = "from .mbar import estimate_mbar\n"
if line not in text:
    text += "\n" + line
path.write_text(text, encoding="utf-8")
PY

