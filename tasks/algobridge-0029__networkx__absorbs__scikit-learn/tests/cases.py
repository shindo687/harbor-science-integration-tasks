"""Deterministic hidden graph fixtures for ALGOBRIDGE-0029."""

from __future__ import annotations

import math
import random


def _case(name, nodes, edges, n_clusters, seed, eigen_tol=1e-10):
    return {
        "name": name,
        "nodes": list(nodes),
        "edges": [[u, v, float(w)] for u, v, w in edges],
        "n_clusters": int(n_clusters),
        "seed": int(seed),
        "eigen_tol": float(eigen_tol),
    }


def _clique_edges(group, weight=1.0):
    return [(u, v, weight) for index, u in enumerate(group) for v in group[index + 1 :]]


def _weak_blocks(name, sizes, seed, bridge_weight=0.0125):
    groups = []
    start = 0
    for size in sizes:
        groups.append(tuple(range(start, start + size)))
        start += size
    edges = []
    for block_index, group in enumerate(groups):
        for edge_index, (u, v, _) in enumerate(_clique_edges(group)):
            weight = 0.8 + 0.04 * ((edge_index + 3 * block_index) % 6)
            edges.append((u, v, weight))
    for index in range(len(groups) - 1):
        edges.append((groups[index][-1], groups[index + 1][0], bridge_weight))
    return _case(name, range(start), edges, len(groups), seed), groups


def _two_moons():
    count = 31
    points = []
    for i in range(count):
        angle = math.pi * i / (count - 1)
        points.append((math.cos(angle), math.sin(angle)))
    for i in range(count):
        angle = math.pi * i / (count - 1)
        points.append((1.08 - math.cos(angle), 0.42 - math.sin(angle)))
    edges = []
    for i, (xi, yi) in enumerate(points):
        nearest = sorted(
            ((xi - xj) ** 2 + (yi - yj) ** 2, j)
            for j, (xj, yj) in enumerate(points)
            if j != i
        )[:5]
        for distance2, j in nearest:
            if i < j:
                edges.append((i, j, math.exp(-distance2 / 0.09)))
            elif not any(u == j and v == i for u, v, _ in edges):
                edges.append((j, i, math.exp(-distance2 / 0.09)))
    return _case("two_moons_62", range(2 * count), edges, 2, 101)


def _stochastic_blocks():
    rng = random.Random(20260813)
    sizes = (13, 16, 11)
    groups = []
    cursor = 0
    for size in sizes:
        groups.append(tuple(range(cursor, cursor + size)))
        cursor += size
    edges = []
    for group in groups:
        for index, u in enumerate(group):
            v = group[(index + 1) % len(group)]
            if u < v or index == len(group) - 1:
                edges.append((u, v, 1.25))
        for i, u in enumerate(group):
            for v in group[i + 2 :]:
                if rng.random() < 0.64:
                    edges.append((u, v, 0.7 + 0.6 * rng.random()))
    for left_index, left in enumerate(groups):
        for right in groups[left_index + 1 :]:
            for u in left:
                for v in right:
                    if rng.random() < 0.018:
                        edges.append((u, v, 0.025 + 0.015 * rng.random()))
    return _case("weighted_sbm_3", range(cursor), edges, 3, 103)


def _disconnected():
    case, _ = _weak_blocks("disconnected_3", (7, 9, 11), 107, bridge_weight=0.0)
    case["edges"] = [edge for edge in case["edges"] if edge[2] != 0.0]
    return case


def _isolates():
    left = tuple(range(7))
    right = tuple(range(7, 15))
    nodes = tuple(range(17))
    edges = _clique_edges(left, 1.0) + _clique_edges(right, 0.9)
    return _case("two_blocks_two_isolates", nodes, edges, 4, 109)


def _weighted_ties():
    left = tuple(range(10))
    right = tuple(range(10, 20))
    edges = []
    for group in (left, right):
        for i, u in enumerate(group):
            edges.append((u, group[(i + 1) % len(group)], 1.0))
            edges.append((u, group[(i + 2) % len(group)], 0.5))
    edges.extend([(4, 14, 0.01), (5, 15, 0.01)])
    return _case("weighted_symmetric_ties", range(20), edges, 2, 113)


def _degenerate_zero_space():
    groups = tuple(tuple(range(6 * i, 6 * (i + 1))) for i in range(4))
    edges = []
    for group in groups:
        for index, u in enumerate(group):
            edges.append((u, group[(index + 1) % len(group)], 1.0))
    return _case("degenerate_zero_eigenspace", range(24), edges, 4, 127)


def _heterogeneous_stars():
    nodes = tuple(range(26))
    edges = []
    for center, leaves in ((0, range(1, 13)), (13, range(14, 26))):
        leaf_list = list(leaves)
        for index, leaf in enumerate(leaf_list):
            edges.append((center, leaf, 0.7 + 0.08 * (index % 5)))
            edges.append((leaf, leaf_list[(index + 1) % len(leaf_list)], 0.35))
    edges.append((0, 13, 0.008))
    return _case("heterogeneous_degree", nodes, edges, 2, 131)


def _path_segments():
    nodes = tuple(range(27))
    edges = []
    for u in range(26):
        weight = 0.008 if u in {8, 17} else 0.8 + 0.1 * (u % 4)
        edges.append((u, u + 1, weight))
    return _case("three_path_segments", nodes, edges, 3, 137)


def _ring_cliques():
    groups = tuple(tuple(range(6 * i, 6 * (i + 1))) for i in range(5))
    edges = []
    for group in groups:
        edges.extend(_clique_edges(group, 1.0))
    for index, group in enumerate(groups):
        edges.append((group[-1], groups[(index + 1) % len(groups)][0], 0.006))
    return _case("ring_of_five_cliques", range(30), edges, 5, 139)


def _grid_halves():
    rows, columns = 6, 8
    nodes = tuple(range(rows * columns))
    edges = []
    for row in range(rows):
        for column in range(columns):
            node = row * columns + column
            if row + 1 < rows:
                edges.append((node, node + columns, 1.0))
            if column + 1 < columns:
                weight = 0.018 if column == columns // 2 - 1 else 1.0
                edges.append((node, node + 1, weight))
    return _case("weighted_grid_halves", nodes, edges, 2, 149)


def _barbell_path():
    left = tuple(range(8))
    path = tuple(range(8, 15))
    right = tuple(range(15, 23))
    edges = _clique_edges(left, 1.0) + _clique_edges(right, 1.0)
    chain = (left[-1],) + path + (right[0],)
    edges.extend((u, v, 0.28) for u, v in zip(chain, chain[1:]))
    return _case("barbell_with_path", range(23), edges, 2, 151)


def _four_weighted_blocks():
    case, _ = _weak_blocks("four_weighted_blocks", (8, 10, 9, 11), 157, 0.007)
    return case


def hidden_cases():
    """Return fresh JSON-compatible specifications for 12 differential cases."""
    return [
        _two_moons(),
        _stochastic_blocks(),
        _disconnected(),
        _isolates(),
        _weighted_ties(),
        _degenerate_zero_space(),
        _heterogeneous_stars(),
        _path_segments(),
        _ring_cliques(),
        _grid_halves(),
        _barbell_path(),
        _four_weighted_blocks(),
    ]


def insertion_order_variant(case):
    """Return the same graph with reversed insertion order and edge direction."""
    # NetworkX Graph applies the last value when an edge appears more than
    # once.  Canonicalize that final simple-graph state before changing order,
    # otherwise reversing a fixture with repeated construction edges would
    # accidentally change its weights instead of only its insertion order.
    final_edges = {}
    for u, v, weight in case["edges"]:
        key = tuple(sorted((u, v), key=lambda node: (type(node).__name__, repr(node))))
        final_edges[key] = float(weight)
    variant = dict(case)
    variant["name"] = case["name"] + "__reversed_insertion"
    variant["nodes"] = list(reversed(case["nodes"]))
    variant["edges"] = [
        [v, u, weight] for (u, v), weight in reversed(list(final_edges.items()))
    ]
    return variant
