#!/usr/bin/env python3
"""Check the five public examples against a candidate complex_metrics module."""
from __future__ import annotations

import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODULE_PATH = Path(sys.argv[1])
ATOL = 5e-4
RTOL = 5e-4


def close(actual, expected, path="root"):
    if isinstance(actual, bool) or isinstance(expected, bool):
        if actual != expected:
            raise AssertionError(f"{path}: {actual!r} != {expected!r}")
    elif isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        if not math.isclose(float(actual), float(expected), abs_tol=ATOL, rel_tol=RTOL):
            raise AssertionError(f"{path}: {actual} != {expected}")
    elif isinstance(actual, dict) and isinstance(expected, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"{path}: key mismatch {set(actual) ^ set(expected)}")
        for key in expected:
            close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            close(left, right, f"{path}[{index}]")
    elif actual != expected:
        raise AssertionError(f"{path}: {actual!r} != {expected!r}")


spec = importlib.util.spec_from_file_location("candidate_complex_metrics", MODULE_PATH)
if spec is None or spec.loader is None:
    raise SystemExit(f"cannot load {MODULE_PATH}")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
for index, item in enumerate(manifest):
    case = ROOT / item["name"]
    scores = json.loads((case / "scores.json").read_text(encoding="utf-8"))
    expected = json.loads((case / "expected.json").read_text(encoding="utf-8"))
    actual = {
        "dockq": module.score_dockq(case / "model.pdb", case / "native.pdb"),
        "ipsae": module.score_ipsae(
            scores["pae"],
            scores["plddt"],
            case / "model.pdb",
            item["pae_cutoff"],
            item["distance_cutoff"],
            scores.get("iptm"),
        ),
    }
    close(actual, expected, item["name"])

    if index == 0:
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "output.json"
            subprocess.run(
                [
                    sys.executable,
                    str(MODULE_PATH),
                    "--model-pdb",
                    str(case / "model.pdb"),
                    "--native-pdb",
                    str(case / "native.pdb"),
                    "--scores-json",
                    str(case / "scores.json"),
                    "--pae-cutoff",
                    str(item["pae_cutoff"]),
                    "--distance-cutoff",
                    str(item["distance_cutoff"]),
                    "--output",
                    str(output),
                ],
                check=True,
            )
            output_text = output.read_text(encoding="utf-8")
            if "NaN" in output_text or "Infinity" in output_text:
                raise AssertionError("CLI emitted non-standard JSON")
            close(json.loads(output_text), expected, "combined CLI")
    print(f"PASS {item['name']}")

print(f"All {len(manifest)} public examples passed")

