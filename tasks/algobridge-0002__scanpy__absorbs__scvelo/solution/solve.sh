#!/bin/sh
set -eu

cp /solution/_velocity_transition.py /testbed/src/scanpy/tools/_velocity_transition.py
cp /solution/test_velocity_transition.py /testbed/src/scanpy/tools/test_velocity_transition.py
python - <<'PY'
from pathlib import Path

path = Path("/testbed/src/scanpy/tools/__init__.py")
text = path.read_text(encoding="utf-8")
import_line = "from ._velocity_transition import velocity_transition_graph\n"
if import_line not in text:
    marker = "from ._umap import umap\n"
    text = text.replace(marker, marker + import_line, 1)
if '    "velocity_transition_graph",\n' not in text:
    text = text.replace('    "umap",\n', '    "umap",\n    "velocity_transition_graph",\n', 1)
path.write_text(text, encoding="utf-8")
PY
