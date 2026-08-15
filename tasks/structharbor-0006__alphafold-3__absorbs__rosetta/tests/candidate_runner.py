#!/usr/bin/env python3
"""JSON-lines adapter for the candidate AlphaFold 3 module."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


MODULE = Path("/testbed/src/alphafold3/model/interface_energy_lite.py")


def main() -> None:
    spec = importlib.util.spec_from_file_location("af3_interface_energy_lite", MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load candidate module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    payload = json.load(sys.stdin)
    json.dump(module.score_interface(payload), sys.stdout, allow_nan=False,
              separators=(",", ":"))
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
