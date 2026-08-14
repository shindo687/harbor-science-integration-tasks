#!/usr/bin/env python3
"""Execute the compiled native GROMACS BAR command for verifier requests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


GROMACS = Path(os.environ.get("CANDIDATE_GMX", "/opt/candidate-build/bin/gmx"))


def serialize(spec):
    return "\n".join([
        "BAR_INTERNAL_V1",
        f"relative_tolerance {float(spec['relative_tolerance']):.17g}",
        f"maximum_iterations {int(spec['maximum_iterations'])}",
        f"initial_delta_f {float(spec['initial_delta_f']):.17g}",
        f"forward {len(spec['forward'])}",
        " ".join(f"{float(value):.17g}" for value in spec["forward"]),
        f"reverse {len(spec['reverse'])}",
        " ".join(f"{float(value):.17g}" for value in spec["reverse"]),
        "",
    ])


def run_one(spec, root):
    source = root / f"{spec['name']}.bar"
    output = root / f"{spec['name']}.json"
    content = spec.get("raw_input")
    source.write_text(serialize(spec) if content is None else content)
    arguments = spec.get(
        "arguments", ["bar-internal", "-f", "{input}", "-o", "{output}"]
    )
    arguments = [
        str(source) if value == "{input}" else
        str(output) if value == "{output}" else str(value)
        for value in arguments
    ]
    completed = subprocess.run(
        [str(GROMACS), *arguments],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=False,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(root),
            "GMX_MAXBACKUP": "-1",
            "GMX_NO_QUOTES": "1",
            "OMP_NUM_THREADS": "1",
        },
    )
    item = {
        "name": spec["name"],
        "returncode": completed.returncode,
        "output_exists": output.is_file(),
        "stdout_tail": completed.stdout[-500:],
        "stderr_tail": completed.stderr[-1000:],
    }
    if completed.returncode == 0 and output.is_file():
        try:
            item["result"] = json.loads(output.read_text())
        except (OSError, json.JSONDecodeError) as error:
            item["protocol_error"] = type(error).__name__
    return item


def main():
    request = json.load(sys.stdin)
    if not GROMACS.is_file():
        raise SystemExit(f"candidate GROMACS binary is missing: {GROMACS}")
    with tempfile.TemporaryDirectory(prefix="algobridge0017-candidate-") as directory:
        response = {
            "cases": [run_one(case, Path(directory)) for case in request["cases"]]
        }
    json.dump(response, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
