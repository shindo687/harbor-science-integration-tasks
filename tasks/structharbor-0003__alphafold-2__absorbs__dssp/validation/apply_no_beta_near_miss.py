#!/usr/bin/env python3
"""Install an otherwise accurate implementation with beta bridges disabled."""

from pathlib import Path
import sys


root = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
source = Path(__file__).resolve().parents[1] / "solution/secondary_structure.py"
text = source.read_text()
needle = '        kind = bridge_kind(i, j)\n'
if text.count(needle) != 1:
    raise SystemExit("solution anchor changed")
text = text.replace(needle, '        kind = None  # deliberate scientific near miss\n')
target = root / "alphafold/common/secondary_structure.py"
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(text)

