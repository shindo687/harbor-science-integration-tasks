#!/usr/bin/env python3
"""Regenerate frozen public outputs using only the locked reference runner."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from public_cases import public_cases


REFERENCE_PYTHON = "/opt/reference-venv/bin/python"
REFERENCE_RUNNER = "/opt/reference-runner/reference_runner.py"
OUTPUT = Path("/examples/expected.json")


expected = {}
for spec in public_cases():
    completed = subprocess.run(
        [REFERENCE_PYTHON, REFERENCE_RUNNER],
        input=json.dumps(spec),
        capture_output=True,
        text=True,
        check=True,
    )
    result = json.loads(completed.stdout)
    expected[spec["name"]] = result

OUTPUT.write_text(json.dumps(expected, indent=2, sort_keys=True) + "\n")
print(f"wrote {len(expected)} locked reference outputs to {OUTPUT}")

