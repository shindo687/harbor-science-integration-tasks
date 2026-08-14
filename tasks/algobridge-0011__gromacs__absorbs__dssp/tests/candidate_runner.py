#!/usr/bin/env python3
"""Execute the compiled native GROMACS DSSP command for verifier requests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


GROMACS = Path(os.environ.get("CANDIDATE_GMX", "/opt/candidate-build/bin/gmx"))
ATOMS = ("N", "CA", "C", "O")


def number(value):
    try:
        return f"{float(value):.17g}"
    except (TypeError, ValueError, OverflowError):
        return str(value)


def serialize(case):
    topology = case.get("topology", [])
    frames = case.get("frames", [])
    schema = case.get("schema", "")
    schema_token = ("DSSP_INTERNAL_V1"
                    if schema == "algobridge-gromacs-dssp-v1" else str(schema))
    lines = [
        schema_token,
        f"energy_cutoff {number(case.get('energy_cutoff'))}",
        f"residues {len(topology)}",
        f"frames {len(frames)}",
    ]
    for residue in topology:
        insertion = residue.get("insertion_code", "") or "_"
        lines.append(" ".join([
            "residue", str(residue.get("chain_id", "_")),
            str(residue.get("residue_index", 0)), insertion,
            str(residue.get("residue_name", "_")),
        ]))
    for frame in frames:
        lines.append(f"frame {number(frame.get('time_ps'))}")
        box = frame.get("box_nm", [])
        lines.append("box " + " ".join(number(value) for value in box))
        for group in frame.get("coordinates_nm", []):
            fields = ["atoms"]
            for atom in ATOMS:
                xyz = group.get(atom) if isinstance(group, dict) else None
                if xyz is None:
                    fields.append("0")
                else:
                    fields.append("1")
                    fields.extend(number(value) for value in xyz)
            lines.append(" ".join(fields))
            if isinstance(group, dict):
                for extra in sorted(set(group) - set(ATOMS)):
                    lines.append(f"unexpected_atom {extra}")
    return "\n".join(lines) + "\n"


def run_one(case, root):
    source = root / f"{case.get('name', 'case')}.dsspint"
    output = root / f"{case.get('name', 'case')}.json"
    source.write_text(case.get("raw_input", serialize(case)))
    arguments = case.get(
        "arguments", ["dssp-internal", "-f", "{input}", "-o", "{output}"])
    arguments = [
        str(source) if value == "{input}" else
        str(output) if value == "{output}" else str(value)
        for value in arguments
    ]
    completed = subprocess.run(
        [str(GROMACS), *arguments], text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=180, check=False,
        env={
            "PATH": "/usr/bin:/bin", "HOME": str(root), "TMPDIR": str(root),
            "GMX_MAXBACKUP": "-1", "GMX_NO_QUOTES": "1", "OMP_NUM_THREADS": "1",
        },
    )
    item = {
        "name": case.get("name"), "returncode": completed.returncode,
        "output_exists": output.is_file(), "stdout_tail": completed.stdout[-500:],
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
    with tempfile.TemporaryDirectory(prefix="algobridge0011-candidate-") as directory:
        response = {"cases": [run_one(case, Path(directory))
                              for case in request["cases"]]}
    json.dump(response, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
