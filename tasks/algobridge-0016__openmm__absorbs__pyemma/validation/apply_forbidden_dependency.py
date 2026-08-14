#!/usr/bin/env python3
"""Install an otherwise complete submission that attempts to import PyEMMA."""

from pathlib import Path


source = Path("/solution/markov_model.py").read_text(encoding="utf-8")
target = Path("/testbed/wrappers/python/openmm/app/markov_model.py")
target.write_text("import pyemma\n" + source, encoding="utf-8")

init = Path("/testbed/wrappers/python/openmm/app/__init__.py")
text = init.read_text(encoding="utf-8")
export = "from .markov_model import estimate_markov_model\n"
if export not in text:
    init.write_text(text + "\n" + export, encoding="utf-8")

