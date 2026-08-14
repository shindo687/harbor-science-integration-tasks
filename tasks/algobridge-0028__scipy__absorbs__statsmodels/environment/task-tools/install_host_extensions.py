#!/usr/bin/env python3
"""Add trusted exact-wheel generated files to the editable Agent tree."""

from __future__ import annotations

import importlib.metadata
from pathlib import Path
import shutil


installed = Path(
    importlib.metadata.distribution("scipy").locate_file("scipy")
).resolve()
target = Path("/testbed/scipy")
for source in installed.rglob("*"):
    if not source.is_file():
        continue
    destination = target / source.relative_to(installed)
    if source.suffix == ".so" or (
        source.suffix == ".py" and not destination.exists()
    ):
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
