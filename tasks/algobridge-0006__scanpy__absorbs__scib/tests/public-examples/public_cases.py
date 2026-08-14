"""Five visible examples; hidden values and sizes are different."""

from __future__ import annotations

import importlib.util
from pathlib import Path


def public_cases():
    cases_path = Path(__file__).resolve().parents[1] / "cases.py"
    spec = importlib.util.spec_from_file_location("task_cases", cases_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.public_cases()

