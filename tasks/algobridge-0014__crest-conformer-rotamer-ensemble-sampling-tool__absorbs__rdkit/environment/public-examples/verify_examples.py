#!/usr/bin/env python3
"""Run the submitted ETKDG kernel against five disclosed examples."""

from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path


MODULE = Path("/testbed/src/etkdg_init.py")


def distance(first, second):
    return math.sqrt(sum((first[k] - second[k]) ** 2 for k in range(3)))


def matrix(coords, indices):
    return [[distance(coords[i], coords[j]) for j in indices] for i in indices]


def drms(first, second):
    values = [(first[i][j] - second[i][j]) ** 2
              for i in range(len(first)) for j in range(i + 1, len(first))]
    return math.sqrt(sum(values) / max(1, len(values)))


def volume(coords, item):
    origin = coords[item["center"]]
    a, b, c = [[coords[index][k] - origin[k] for k in range(3)]
               for index in item["neighbors"]]
    cross = [b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0]]
    return sum(a[k] * cross[k] for k in range(3))


def check(packet, expected, result):
    size = len(packet["atomic_numbers"])
    bound_delta = max(abs(result["bounds"][key][i][j] - expected[f"smoothed_{key}"][i][j])
                      for key in ("lower", "upper") for i in range(size) for j in range(size))
    conformers = result["conformers"]
    if not expected["native_count"] <= len(conformers) <= packet["num_confs"]:
        return math.inf
    violation = 0.0
    candidate = []
    for coords in conformers:
        for i in range(size):
            for j in range(i + 1, size):
                value = distance(coords[i], coords[j])
                violation = max(violation, expected["smoothed_lower"][i][j] - value,
                                value - expected["smoothed_upper"][i][j])
        if any(item["sign"] * volume(coords, item) < item["min_volume"] * 0.95
               for item in packet["chiral_constraints"]):
            return math.inf
        candidate.append(matrix(coords, packet["prune_atoms"]))
    coverage = max((min(drms(native, value) for value in candidate)
                    for native in expected["native_distance_matrices"]), default=math.inf)
    return max(bound_delta / 1e-9, violation / 0.35, coverage / 0.80)


def main():
    spec = importlib.util.spec_from_file_location("crest_etkdg", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    failures = 0
    for path in sorted(Path("/examples").glob("[0-9][0-9]-*.json")):
        example = json.loads(path.read_text())
        result = module.embed_etkdg(example["input"]["packet"])
        ratio = check(example["input"]["packet"], example["expected"], result)
        passed = ratio <= 1.0
        failures += not passed
        print(f"{'PASS' if passed else 'FAIL'} {example['input']['name']} normalized_error={ratio:.3g}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
