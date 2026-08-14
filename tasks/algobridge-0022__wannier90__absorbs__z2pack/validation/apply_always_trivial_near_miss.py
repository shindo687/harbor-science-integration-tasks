#!/usr/bin/env python3
"""Create a plausible incomplete variant that computes WCC but forces Z2=0."""

from pathlib import Path
import sys


if len(sys.argv) != 3:
    raise SystemExit("usage: apply_always_trivial_near_miss.py SOURCE DEST")

source = Path(sys.argv[1]).read_text()
needle = "    if (parity == -1) z2 = 1\n"
if source.count(needle) != 1:
    raise SystemExit("expected parity assignment not found exactly once")
Path(sys.argv[2]).write_text(source.replace(needle, "    z2 = 0 ! Deliberately incomplete near-miss.\n"))

