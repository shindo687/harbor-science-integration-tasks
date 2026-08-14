#!/usr/bin/env python3
"""Run the public examples against a candidate NetworkX checkout."""

from __future__ import annotations

import argparse
import math
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def canonical_groups(partition):
    grouped = {}
    for node, label in partition.items():
        grouped.setdefault(int(label), []).append(node)
    return sorted((tuple(sorted(nodes, key=repr)) for nodes in grouped.values()), key=repr)


def expected_ncut(graph, groups, weight="weight"):
    total = 0.0
    all_nodes = set(graph)
    for raw_group in groups:
        group = set(raw_group)
        volume = sum(
            data.get(weight, 1.0)
            for node in group
            for _, _, data in graph.edges(node, data=True)
        )
        cut = sum(
            data.get(weight, 1.0)
            for u, v, data in graph.edges(data=True)
            if (u in group) != (v in group)
        )
        if volume:
            total += cut / volume
        assert group <= all_nodes
    return total


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", nargs="?", default="/testbed")
    args = parser.parse_args()
    sys.path.insert(0, str(pathlib.Path(args.checkout).resolve()))
    sys.path.insert(0, str(HERE))

    import networkx as nx
    import numpy as np
    from public_cases import CASES, load_case

    failures = []
    for name in CASES:
        graph, n_clusters, seed, expected_groups = load_case(name)
        result = nx.spectral_clustering(graph, n_clusters, seed=seed)
        expected = sorted(
            (tuple(sorted(group, key=repr)) for group in expected_groups), key=repr
        )
        actual = canonical_groups(result["partition"])
        expected_score = expected_ncut(graph, expected_groups)
        shape = np.asarray(result["embedding"]).shape
        ok = (
            actual == expected
            and shape == (len(graph), n_clusters)
            and len(result["eigenvalues"]) == n_clusters
            and math.isclose(
                float(result["normalized_cut"]), expected_score, rel_tol=0.0, abs_tol=1e-8
            )
        )
        print(f"{name}: {'PASS' if ok else 'FAIL'}")
        if not ok:
            failures.append((name, actual, expected, result["normalized_cut"], expected_score))

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        raise SystemExit(1)
    print(f"public examples: {len(CASES)}/{len(CASES)}")


if __name__ == "__main__":
    main()
