#!/usr/bin/env python3
"""Deliberately omit BAR's unequal-population correction for control testing."""

from pathlib import Path
import sys


root = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
path = root / "src/gromacs/gmxana/gmx_bar_internal.cpp"
text = path.read_text()
old = """        countOffset_(std::log(static_cast<double>(input.forward.size())
                              / static_cast<double>(input.reverse.size())))
"""
new = """        countOffset_(0.0)
"""
if text.count(old) != 1:
    raise SystemExit("near-miss anchor not found exactly once")
path.write_text(text.replace(old, new, 1))
