#!/usr/bin/env python3
"""Authoring-time real differential matrix for the bounded Oracle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile
from typing import Any

from candidate_runner import candidate_calls
from fixture_factory import make_fixture
from reference_runner import reference_calls


NUMERIC_TOLERANCE = 1e-4


def compare_calls(reference: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    if len(reference) != len(candidate):
        return [f"call count: reference={len(reference)} candidate={len(candidate)}"]
    exact_keys = ("chrom", "pos", "ref", "alt", "dp", "sample_dp", "gt", "ad")
    for index, (expected, actual) in enumerate(zip(reference, candidate, strict=True)):
        for key in exact_keys:
            if expected[key] != actual[key]:
                failures.append(f"call {index} {key}: {expected[key]!r} != {actual[key]!r}")
        for key in ("qual", "gq"):
            if abs(float(expected[key]) - float(actual[key])) > NUMERIC_TOLERANCE:
                failures.append(f"call {index} {key}: {expected[key]!r} != {actual[key]!r}")
        if len(expected["gl"]) != len(actual["gl"]):
            failures.append(f"call {index} GL length differs")
        else:
            for gl_index, (left, right) in enumerate(zip(expected["gl"], actual["gl"], strict=True)):
                if abs(float(left) - float(right)) > NUMERIC_TOLERANCE:
                    failures.append(f"call {index} GL[{gl_index}]: {left!r} != {right!r}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("binary", type=Path)
    parser.add_argument("--section", choices=("public", "hidden", "all"), default="all")
    args = parser.parse_args()
    matrix = json.loads((Path(__file__).with_name("case_specs.json")).read_text(encoding="utf-8"))
    sections = ("public", "hidden") if args.section == "all" else (args.section,)
    passed = 0
    failed = 0
    for section in sections:
        for entry in matrix[section]:
            case_id = str(entry["id"])
            try:
                with tempfile.TemporaryDirectory(prefix=f"algobridge0010-{case_id}-") as temporary:
                    case_dir = Path(temporary)
                    make_fixture(entry["spec"], case_dir)
                    parameters = json.loads((case_dir / "parameters.json").read_text(encoding="utf-8"))
                    expected = reference_calls(case_dir, parameters)
                    actual = candidate_calls(args.binary, case_dir, parameters)
                    failures = compare_calls(expected, actual)
                if failures:
                    failed += 1
                    print(f"FAIL {case_id}")
                    for failure in failures:
                        print(f"  {failure}")
                else:
                    passed += 1
                    print(f"PASS {case_id} ({len(expected)} calls)")
            except Exception as error:  # authoring harness must report the case and continue
                failed += 1
                print(f"ERROR {case_id}: {error}")
    print(f"SUMMARY passed={passed} failed={failed}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
