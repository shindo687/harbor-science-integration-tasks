#!/usr/bin/env python3
"""Run the submitted module against five disclosed MMFF94 packets."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path


MODULE = Path("/testbed/build/python/vina/mmff94.py")
EXAMPLES = Path("/examples")


def load_function():
    spec = importlib.util.spec_from_file_location("vina_mmff94", MODULE)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {MODULE}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.score_mmff94


def main():
    function = load_function()
    failures = 0
    for path in sorted(EXAMPLES.glob("[0-9][0-9]-*.json")):
        example = json.loads(path.read_text())
        result = function(example["input"]["packet"])
        expected = example["expected"]
        if not isinstance(result, dict) or set(result) != set(expected):
            delta = math.inf
        else:
            delta = max(
                abs(float(result[name]) - float(expected[name]))
                for name in expected
            )
        passed = delta <= 1e-7
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'} {example['input']['name']} max_abs={delta:.3g}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
