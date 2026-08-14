#!/usr/bin/env python3
"""Install the clean-room Oracle into a SciPy source tree."""

from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
TESTBED = Path("/testbed")
STATS = TESTBED / "scipy" / "stats"

shutil.copy2(ROOT / "_robust_linear_model.py", STATS / "_robust_linear_model.py")

init_path = STATS / "__init__.py"
contents = init_path.read_text()
import_line = "from ._robust_linear_model import RobustLinearModelResult, robust_linear_model\n"
anchor = "__all__ = [s for s in dir() if not s.startswith(\"_\")]  # Remove dunders.\n"
if import_line not in contents:
    if anchor not in contents:
        raise RuntimeError("unable to find scipy.stats export anchor")
    contents = contents.replace(anchor, import_line + "\n" + anchor)
    init_path.write_text(contents)

