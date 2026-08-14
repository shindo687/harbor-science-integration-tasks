#!/usr/bin/env python3
"""Add trusted exact-wheel extensions to the Agent's editable source tree."""

from __future__ import annotations

import importlib.metadata
import pathlib
import shutil


distribution = importlib.metadata.distribution("scikit-learn")
installed = pathlib.Path(distribution.locate_file("sklearn")).resolve()
target = pathlib.Path("/testbed/sklearn")
for source in installed.rglob("*.so"):
    destination = target / source.relative_to(installed)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
