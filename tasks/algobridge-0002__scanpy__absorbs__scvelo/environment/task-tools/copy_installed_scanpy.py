#!/usr/bin/env python3
"""Copy the exact installed Scanpy package to an immutable overlay base."""

from importlib.util import find_spec
from pathlib import Path
import shutil

import scanpy


target = Path("/opt/installed-scanpy")
target.mkdir(parents=True, exist_ok=True)
sources = [Path(scanpy.__file__).resolve().parent]
testing_spec = find_spec("testing")
if testing_spec is None or not testing_spec.submodule_search_locations:
    raise RuntimeError("installed Scanpy testing namespace is missing")
sources.append(Path(next(iter(testing_spec.submodule_search_locations))).resolve())
for source in sources:
    destination = target / source.name
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
