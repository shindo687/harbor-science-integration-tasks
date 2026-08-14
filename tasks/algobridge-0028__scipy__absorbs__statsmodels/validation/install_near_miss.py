#!/usr/bin/env python3
"""Install the representative OLS-only near miss into /testbed."""

from pathlib import Path
import shutil


root = Path(__file__).resolve().parent
stats = Path("/testbed/scipy/stats")
shutil.copy2(root / "near_miss.py", stats / "_robust_linear_model.py")

init_path = stats / "__init__.py"
contents = init_path.read_text()
line = "from ._robust_linear_model import RobustLinearModelResult, robust_linear_model\n"
anchor = "__all__ = [s for s in dir() if not s.startswith(\"_\")]  # Remove dunders.\n"
if line not in contents:
    contents = contents.replace(anchor, line + "\n" + anchor)
    init_path.write_text(contents)

