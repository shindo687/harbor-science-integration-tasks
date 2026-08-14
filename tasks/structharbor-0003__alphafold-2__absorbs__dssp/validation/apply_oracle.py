#!/usr/bin/env python3
"""Install the independent reference solution into an extracted artifact."""

from pathlib import Path
import shutil
import sys


root = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
source = Path(__file__).resolve().parents[1] / "solution/secondary_structure.py"
target = root / "alphafold/common/secondary_structure.py"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)

