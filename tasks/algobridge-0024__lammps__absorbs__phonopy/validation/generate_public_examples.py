#!/usr/bin/env python3
"""Regenerate the five public examples using only the locked reference path."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import CASE_BY_NAME  # noqa: E402
from reference_runner import generate  # noqa: E402


PUBLIC = [
    "mono_chain_four",
    "square_nine",
    "diatomic_chain",
    "simple_cubic_eight",
    "compressed_imaginary",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lammps", required=True, type=Path)
    args = parser.parse_args()
    public_root = ROOT / "public-examples"
    environment_root = ROOT / "environment/public-examples"
    public_root.mkdir(parents=True, exist_ok=True)
    environment_root.mkdir(parents=True, exist_ok=True)
    for directory in (public_root, environment_root):
        for path in directory.glob("*.json"):
            path.unlink()
        (directory / "SHA256SUMS").unlink(missing_ok=True)

    hashes = []
    with tempfile.TemporaryDirectory(prefix="algobridge0024-public-") as tmp:
        temp_root = Path(tmp)
        for index, name in enumerate(PUBLIC, 1):
            case_root = temp_root / name
            case_root.mkdir()
            candidate_input, expected = generate(CASE_BY_NAME[name], args.lammps.resolve(), case_root)
            payload = {
                "name": name,
                "reference_pipeline": "locked pristine LAMMPS -> locked pristine phonopy",
                "input": candidate_input,
                "expected": expected,
            }
            target = public_root / f"{index:02d}-{name}.json"
            target.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            digest = hashlib.sha256(target.read_bytes()).hexdigest()
            hashes.append(f"{digest}  {target.name}")
            shutil.copy2(target, environment_root / target.name)
    manifest = "\n".join(hashes) + "\n"
    (public_root / "SHA256SUMS").write_text(manifest, encoding="utf-8")
    (environment_root / "SHA256SUMS").write_text(manifest, encoding="utf-8")


if __name__ == "__main__":
    main()

