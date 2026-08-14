#!/usr/bin/env python3
"""Copy trusted wheel extensions into the editable Agent source tree."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
import shutil


distribution = importlib.metadata.distribution("scikit-learn")
installed = Path(distribution.locate_file("sklearn")).resolve()
target = Path("/testbed/sklearn")
copied = []
for source in sorted(installed.rglob("*.so")):
    destination = target / source.relative_to(installed)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    copied.append(str(destination.relative_to("/testbed")))
Path("/opt/task-tools/trusted-extension-manifest.txt").write_text(
    "\n".join(copied) + "\n", encoding="utf-8"
)
