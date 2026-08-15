#!/usr/bin/env python3
"""Execute every public fixture and check the documented output identities."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess


TERMS = {"lj_repulsive", "lj_attractive", "coulomb", "hbond", "sasa"}


def main() -> None:
    for path in sorted(Path("/examples").glob("*.json")):
        packet = json.loads(path.read_text())
        completed = subprocess.run(
            ["python3", "/opt/task-tools/candidate_runner.py"],
            input=json.dumps(packet), text=True, capture_output=True,
            timeout=120, check=False,
        )
        if completed.returncode:
            raise SystemExit(f"FAIL {path.name}: {completed.stderr[-800:]}")
        result = json.loads(completed.stdout)
        if set(result) != {"bound", "unbound", "delta", "per_residue", "forces"}:
            raise SystemExit(f"FAIL {path.name}: output schema")
        for section in ("bound", "unbound", "delta"):
            if set(result[section]["terms"]) != TERMS:
                raise SystemExit(f"FAIL {path.name}: term schema")
            total = sum(result[section]["terms"].values())
            if abs(total - result[section]["total"]) > 1.0e-8:
                raise SystemExit(f"FAIL {path.name}: {section} total identity")
        residue_total = sum(row["total"] for row in result["per_residue"])
        if abs(residue_total - result["delta"]["total"]) > 1.0e-8:
            raise SystemExit(f"FAIL {path.name}: per-residue identity")
        print(f"PASS {path.name} delta={result['delta']['total']:.10g}")


if __name__ == "__main__":
    main()
