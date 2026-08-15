#!/usr/bin/env python3
"""Run the candidate score_interface function for one stdin JSON packet."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


path = Path("/testbed/src/alphafold3/model/interface_energy_lite.py")
spec = importlib.util.spec_from_file_location("af3_interface_energy_lite", path)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load {path}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
json.dump(module.score_interface(json.load(sys.stdin)), sys.stdout, allow_nan=False,
          indent=2, sort_keys=True)
sys.stdout.write("\n")
