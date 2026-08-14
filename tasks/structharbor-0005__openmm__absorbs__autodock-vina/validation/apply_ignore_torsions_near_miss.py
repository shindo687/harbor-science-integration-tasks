#!/usr/bin/env python3
"""Install a plausible near miss that omits Vina torsional normalization."""

from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_ignore_torsions_near_miss.py TESTBED")
    source = (ROOT / "solution" / "vina_score.py").read_text()
    old = "_ROTATABLE_WEIGHT = 0.05846"
    if source.count(old) != 1:
        raise RuntimeError("expected torsional-weight declaration not found")
    destination = (Path(sys.argv[1]) / "wrappers" / "python" / "openmm"
                   / "app" / "vina_score.py")
    destination.write_text(source.replace(old, "_ROTATABLE_WEIGHT = 0.0"))


if __name__ == "__main__":
    main()
