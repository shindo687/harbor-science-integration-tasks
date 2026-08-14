#!/usr/bin/env python3
"""Regenerate public cases and expected outputs using the locked donor."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from cases import PUBLIC_SPECS, make_case, write_case  # noqa: E402
from reference_runner import run_reference  # noqa: E402


def main() -> int:
    output = ROOT / "public-examples"
    output.mkdir(exist_ok=True)
    for old in output.glob("*.json"):
        old.unlink()
    sums = []
    for index, spec in enumerate(PUBLIC_SPECS, 1):
        stem = f"{index:02d}-{spec['name']}"
        input_path = output / f"{stem}.input.json"
        expected_path = output / f"{stem}.expected.json"
        write_case(input_path, make_case(**spec))
        expected_path.write_text(json.dumps(run_reference(input_path), indent=2, sort_keys=True) + "\n")
        for path in (input_path, expected_path):
            sums.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.name}")
    (output / "SHA256SUMS").write_text("\n".join(sums) + "\n")
    for target in (ROOT / "environment/public-examples", ROOT / "tests/public-examples"):
        target.mkdir(parents=True, exist_ok=True)
        for old in target.iterdir():
            if old.is_file():
                old.unlink()
        for source in output.iterdir():
            shutil.copy2(source, target / source.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

