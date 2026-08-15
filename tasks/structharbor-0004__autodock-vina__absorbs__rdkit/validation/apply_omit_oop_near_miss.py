#!/usr/bin/env python3
"""Install a plausible near miss that omits out-of-plane energy."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_omit_oop_near_miss.py TESTBED")
    source = (ROOT / "solution" / "mmff94.py").read_text()
    old = 'energy["out_of_plane"] += 0.5 * _C'
    new = 'energy["out_of_plane"] += 0.0 * _C'
    if source.count(old) != 1:
        raise RuntimeError("expected out-of-plane energy expression not found")
    destination = Path(sys.argv[1]) / "build/python/vina/mmff94.py"
    destination.write_text(source.replace(old, new))


if __name__ == "__main__":
    main()
