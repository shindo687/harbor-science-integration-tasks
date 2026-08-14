#!/usr/bin/env python3
"""Generate five public fixtures through the locked phono3py reference."""

from __future__ import annotations

import json
from pathlib import Path
import sys


sys.path.insert(0, "/repo/tests")
from cases import P1_THREE, P1_TWO, generated, zincblende  # noqa: E402
from reference_runner import jsonify, run_one  # noqa: E402


OUTPUT = Path("/output")


def public_cases():
    return [
        generated("public_p1_two_exact", P1_TWO, 21, 19001),
        generated(
            "public_p1_three_noisy", P1_THREE, 42, 19003, noise=1e-4
        ),
        generated(
            "public_zincblende_projected",
            zincblende(),
            8,
            19007,
            is_symmetry=True,
        ),
        generated(
            "public_zincblende_noisy",
            zincblende(),
            9,
            19009,
            is_symmetry=True,
            amplitude=0.018,
            noise=1.5e-4,
        ),
        generated(
            "public_symmetry_rescued",
            zincblende(),
            3,
            19013,
            is_symmetry=True,
        ),
    ]


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT.glob("[0-9][0-9]-*.json"):
        old.unlink()
    for index, item in enumerate(public_cases(), start=1):
        expected = jsonify(run_one(item))
        path = OUTPUT / f"{index:02d}-{item['name']}.json"
        path.write_text(
            json.dumps({"input": item, "expected": expected}, indent=2) + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
