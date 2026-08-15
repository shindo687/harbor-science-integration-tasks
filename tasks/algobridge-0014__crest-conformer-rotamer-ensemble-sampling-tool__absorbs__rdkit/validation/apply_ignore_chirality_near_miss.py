#!/usr/bin/env python3
"""Install a plausible near miss that ignores chirality metadata."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_ignore_chirality_near_miss.py TESTBED")
    source = (ROOT / "solution/etkdg_init.py").read_text()
    old = 'chirality_value = packet.get("chiral_constraints")'
    new = 'chirality_value = []'
    if source.count(old) != 1:
        raise RuntimeError("expected chirality parser not found")
    destination = Path(sys.argv[1]) / "src/etkdg_init.py"
    destination.write_text(source.replace(old, new))


if __name__ == "__main__":
    main()
