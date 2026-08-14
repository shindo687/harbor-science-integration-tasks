#!/usr/bin/env python3
"""Install an otherwise complete submission that attempts to import ProDy."""

from pathlib import Path


source = Path("/solution/anm.py").read_text(encoding="utf-8")
target = Path("/testbed/python_packaging/gmxapi/src/gmxapi/analysis/anm.py")
init_target = Path(
    "/testbed/python_packaging/gmxapi/src/gmxapi/analysis/__init__.py"
)
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text("import prody\n" + source, encoding="utf-8")
init_target.write_text(
    Path("/solution/__init__.py").read_text(encoding="utf-8"),
    encoding="utf-8",
)
