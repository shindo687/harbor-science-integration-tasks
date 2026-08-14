#!/usr/bin/env python3
"""Install the independent author Oracle into a Scanpy checkout."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


testbed = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
source = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(__file__).with_name("_lisi.py")
target = testbed / "src/scanpy/metrics/_lisi.py"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)

init = testbed / "src/scanpy/metrics/__init__.py"
line = "from ._lisi import lisi_graph_score\n"
text = init.read_text()
if line not in text:
    text = text.replace('from ._metrics import confusion_matrix, modularity\n', 'from ._metrics import confusion_matrix, modularity\n' + line)
    text = text.replace(
        '__all__ = ["confusion_matrix", "gearys_c", "modularity", "morans_i"]',
        '__all__ = ["confusion_matrix", "gearys_c", "lisi_graph_score", "modularity", "morans_i"]',
    )
    init.write_text(text)

