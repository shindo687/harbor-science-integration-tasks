#!/usr/bin/env python3
"""Author-only local differential smoke test for an Oracle checkout."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from candidate_runner import run_case
from cases import hidden_cases
from grader import compare_case


def main():
    checkout = pathlib.Path(sys.argv[1]).resolve()
    cases = hidden_cases()
    reference_environment = os.environ.copy()
    reference_environment["PYTHONPATH"] = str(HERE / "reference/host-source")
    completed = subprocess.run(
        [sys.executable, str(HERE / "reference_runner.py")],
        input=json.dumps({"cases": cases}),
        capture_output=True,
        text=True,
        env=reference_environment,
        check=True,
    )
    references = json.loads(completed.stdout)["results"]

    sys.path.insert(0, str(checkout))
    import networkx as nx

    passed = 0
    for spec, reference in zip(cases, references, strict=True):
        candidate = run_case(nx, spec)
        ok, details = compare_case(reference, candidate)
        print(f"{'PASS' if ok else 'FAIL'} {spec['name']}: {details}")
        passed += int(ok)
    print(f"differential smoke: {passed}/{len(cases)}")
    raise SystemExit(0 if passed == len(cases) else 1)


if __name__ == "__main__":
    main()

