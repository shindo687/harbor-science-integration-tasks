#!/usr/bin/env python3
"""Install an otherwise complete submission that attempts to import ProDy."""

from pathlib import Path


source = Path("/solution/normal_modes.py").read_text(encoding="utf-8")
target = Path("/testbed/alphafold/common/normal_modes.py")
target.write_text("import prody\n" + source, encoding="utf-8")
