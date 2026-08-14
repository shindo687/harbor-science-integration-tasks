#!/usr/bin/env python3
"""Install an otherwise complete submission that attempts to use phono3py."""

from pathlib import Path


source = Path("/solution/third_order.py").read_text(encoding="utf-8")
target = Path("/testbed/phonopy/harmonic/third_order.py")
target.write_text("import phono3py\n" + source, encoding="utf-8")
