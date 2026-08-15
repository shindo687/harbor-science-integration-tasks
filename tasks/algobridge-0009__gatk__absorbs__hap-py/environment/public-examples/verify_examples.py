#!/usr/bin/env python3
"""Compile-free checker used by run-public-examples after javac succeeds."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess


def compare(expected, observed):
    if not observed.get("ok"):
        return False, observed.get("error", "candidate failed")
    result = observed.get("result")
    if not isinstance(result, dict) or set(result) != {"truth", "query", "summary"}:
        return False, "result schema"
    if result["truth"] != expected["truth"] or result["query"] != expected["query"]:
        return False, "allele statuses"
    for key in ("truth_tp", "query_tp", "fp", "fn"):
        if result["summary"].get(key) != expected["summary"][key]:
            return False, key
    for key in ("precision", "recall", "f1"):
        value = result["summary"].get(key)
        if (not isinstance(value, (int, float)) or not math.isfinite(value)
                or abs(value - expected["summary"][key]) > 1.0e-12):
            return False, key
    return True, "pass"


def main():
    classes = os.environ["CANDIDATE_CLASSES"]
    runner = "/opt/task-tools/candidate_runner.py"
    passed = 0
    files = sorted(Path("/examples").glob("[0-9][0-9]-*.json"))
    for path in files:
        value = json.loads(path.read_text())
        completed = subprocess.run(
            ["python", runner], input=json.dumps(value["packet"]) + "\n",
            text=True, capture_output=True, timeout=30, check=False,
            env={**os.environ, "CANDIDATE_CLASSES": classes},
        )
        if completed.returncode or len(completed.stdout.strip().splitlines()) != 1:
            print(f"FAIL {value['packet']['name']}: runner failure")
            continue
        observed = json.loads(completed.stdout)
        good, reason = compare(value["expected"], observed)
        print(("PASS" if good else "FAIL") + f" {value['packet']['name']}: {reason}")
        passed += int(good)
    print(f"public examples: {passed}/{len(files)}")
    raise SystemExit(0 if files and passed == len(files) else 1)


if __name__ == "__main__":
    main()
