#!/usr/bin/env python3
"""Materialize the five documented examples using the real reference image."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


sys.path.insert(0, "/tests")

from fixture_factory import make_fixture  # noqa: E402
from reference_runner import reference_calls  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    matrix = json.loads(Path("/tests/case_specs.json").read_text(encoding="utf-8"))
    args.output.mkdir(parents=True, exist_ok=True)
    for entry in matrix["public"]:
        case_id = str(entry["id"])
        case_dir = args.output / case_id
        make_fixture(entry["spec"], case_dir)
        parameters = json.loads((case_dir / "parameters.json").read_text(encoding="utf-8"))
        payload = {
            "schema_version": 1,
            "reference_pipeline": "pristine BWA-MEM 0.7.17 -> samtools 1.13 -> real FreeBayes 1.3.6",
            "calls": reference_calls(case_dir, parameters),
        }
        (case_dir / "expected.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
