#!/usr/bin/env python3
"""Unprivileged line-oriented wrapper for submitted PDB2PQR code."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys


MODULE = Path("/testbed/pdb2pqr/lpbe_grid.py")


def load_module():
    spec = importlib.util.spec_from_file_location("pdb2pqr_lpbe_grid", MODULE)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load submitted module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    module = load_module()
    for line in sys.stdin:
        try:
            request = json.loads(line)
            result = module.solve_lpbe(request["packet"])
            print(json.dumps({"ok": True, "result": result}, separators=(",", ":")), flush=True)
        except Exception as error:
            print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}), flush=True)


if __name__ == "__main__":
    main()
