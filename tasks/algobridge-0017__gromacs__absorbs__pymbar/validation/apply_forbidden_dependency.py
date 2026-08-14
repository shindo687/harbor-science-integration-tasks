#!/usr/bin/env python3
"""Inject an explicit forbidden donor dependency marker for gate testing."""

from pathlib import Path
import sys


root = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
path = root / "src/gromacs/gmxana/gmx_bar_internal.cpp"
text = path.read_text()
anchor = "/* Native bounded Bennett acceptance-ratio analysis for GROMACS. */"
if text.count(anchor) != 1:
    raise SystemExit("forbidden-control anchor not found exactly once")
path.write_text(text.replace(anchor, anchor + "\n/* forbidden runtime: pymbar */", 1))
