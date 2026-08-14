#!/usr/bin/env python3
"""Run the five published DSSP examples against a built candidate GROMACS."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


GROMACS = Path(os.environ.get("CANDIDATE_GMX", "/testbed/build-public/bin/gmx"))
ROOT = Path("/opt/public-examples")
ATOMS = ("N", "CA", "C", "O")


def number(value):
    try:
        return f"{float(value):.17g}"
    except (TypeError, ValueError, OverflowError):
        return str(value)


def serialize(case):
    topology = case["topology"]
    frames = case["frames"]
    lines = [
        "DSSP_INTERNAL_V1", f"energy_cutoff {number(case['energy_cutoff'])}",
        f"residues {len(topology)}", f"frames {len(frames)}",
    ]
    for residue in topology:
        insertion = residue["insertion_code"] or "_"
        lines.append(
            f"residue {residue['chain_id']} {residue['residue_index']} "
            f"{insertion} {residue['residue_name']}"
        )
    for frame in frames:
        lines.append(f"frame {number(frame['time_ps'])}")
        lines.append("box " + " ".join(number(value) for value in frame["box_nm"]))
        for group in frame["coordinates_nm"]:
            fields = ["atoms"]
            for atom in ATOMS:
                xyz = group.get(atom)
                if xyz is None:
                    fields.append("0")
                else:
                    fields.extend(["1", *(number(value) for value in xyz)])
            lines.append(" ".join(fields))
    return "\n".join(lines) + "\n"


def equivalent(actual, expected):
    if set(actual) != set(expected):
        return False
    if actual.keys() - {"frames"} and any(
        actual[key] != expected[key] for key in actual if key != "frames"
    ):
        return False
    if len(actual["frames"]) != len(expected["frames"]):
        return False
    for got, want in zip(actual["frames"], expected["frames"], strict=True):
        if set(got) != set(want):
            return False
        for key in got:
            if key in {"acceptor_energy", "donor_energy"}:
                for got_row, want_row in zip(got[key], want[key], strict=True):
                    for left, right in zip(got_row, want_row, strict=True):
                        if not (math.isfinite(float(left))
                                and abs(float(left) - float(right)) <= 1e-3):
                            return False
            elif got[key] != want[key]:
                return False
    return True


def main():
    if not GROMACS.is_file():
        raise SystemExit(f"candidate binary is missing: {GROMACS}")
    files = sorted(ROOT.glob("[0-9][0-9]-*.json"))
    passed = 0
    with tempfile.TemporaryDirectory(prefix="algobridge0011-public-") as directory:
        work = Path(directory)
        for path in files:
            document = json.loads(path.read_text())
            source = work / f"{path.stem}.dsspint"
            output = work / f"{path.stem}.json"
            source.write_text(serialize(document["case"]))
            completed = subprocess.run(
                [str(GROMACS), "dssp-internal", "-f", str(source), "-o", str(output)],
                text=True, capture_output=True, timeout=180, check=False,
                env={"PATH": "/usr/bin:/bin", "HOME": str(work), "TMPDIR": str(work),
                     "GMX_MAXBACKUP": "-1", "GMX_NO_QUOTES": "1", "OMP_NUM_THREADS": "1"},
            )
            ok = completed.returncode == 0 and output.is_file()
            if ok:
                try:
                    ok = equivalent(json.loads(output.read_text()), document["expected"])
                except (OSError, ValueError, TypeError, KeyError):
                    ok = False
            passed += int(ok)
            print(f"{'PASS' if ok else 'FAIL'} {document['case']['name']}")
    print(f"public examples: {passed}/{len(files)}")
    raise SystemExit(0 if passed == len(files) and len(files) == 5 else 1)


if __name__ == "__main__":
    main()
