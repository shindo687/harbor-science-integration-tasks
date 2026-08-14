#!/usr/bin/env python3
"""Create a plausible incomplete variant that assumes every pair is FM."""

from pathlib import Path
import sys


if len(sys.argv) != 3:
    raise SystemExit(
        "usage: apply_always_ferromagnetic_sign_near_miss.py SOURCE DEST"
    )

source = Path(sys.argv[1]).read_text()
needle = """          if (moments_z(i) * moments_z(j) >= 0.0_real64) then
            sign_pair = 1.0_real64
          else
            sign_pair = -1.0_real64
          end if
"""
replacement = """          sign_pair = 1.0_real64 ! Deliberately incomplete near-miss.
"""
if source.count(needle) != 1:
    raise SystemExit("expected magnetic-pair sign block not found exactly once")
Path(sys.argv[2]).write_text(source.replace(needle, replacement))
