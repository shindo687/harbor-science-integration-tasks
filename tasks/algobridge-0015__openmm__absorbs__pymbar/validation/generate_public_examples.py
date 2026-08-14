#!/usr/bin/env python3
"""Author-only generator for the five locked public examples."""

from __future__ import annotations

import json
from pathlib import Path

from cases import _case
from reference_runner import solve


CASES = [
    _case("public_symmetric_pair", [-0.3, 0.3], [1.0, 1.0], [12, 12], 2501),
    _case("public_unequal_pair", [-0.8, 0.7], [0.8, 1.5], [9, 21], 2502),
    _case("public_three_bridge", [-1.2, 0.0, 1.2], [1.2, 0.9, 1.4],
          [10, 12, 10], 2503),
    _case("public_unsampled_state", [-1.0, 0.2, 1.1], [1.0, 1.3, 0.8],
          [14, 0, 14], 2504),
    _case("public_warm_start", [-0.5, 0.4, 1.0], [0.7, 1.1, 1.8],
          [16, 18, 16], 2505, initial_f_k=[0.0, 1.5, -0.5]),
]


def main():
    target = Path("/output")
    target.mkdir(parents=True, exist_ok=True)
    for index, case in enumerate(CASES, start=1):
        payload = solve(case)
        path = target / f"{index:02d}-{case['name']}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
