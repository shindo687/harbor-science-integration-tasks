"""Deterministic graph-distance fixtures for ALGOBRIDGE-0006."""

from __future__ import annotations

import math
import random


def _case(
    name,
    n,
    edges,
    batch,
    cell_type,
    *,
    n_neighbors,
    perplexity,
    preserve_ties=False,
):
    weights = {}
    for left, right, weight in edges:
        left, right = int(left), int(right)
        value = float(weight)
        if left == right:
            continue
        key = (left, right) if left < right else (right, left)
        # scIB's bounded C++ shortest-path implementation has no explicit
        # index tie-break at the k-neighbor boundary.  Most fixtures therefore
        # use a visible deterministic perturbation so the metric, rather than
        # an incidental heap layout, defines the expected answer.  Dedicated
        # repeated-distance cases retain exact ties with category-symmetric
        # labels.
        if not preserve_ties:
            value += 1e-4 * (1 + ((key[0] + 1) * 97 + (key[1] + 1) * 193) % 89)
        weights[key] = min(value, weights.get(key, math.inf))

    rows = [[] for _ in range(n)]
    for (left, right), value in weights.items():
        rows[left].append((right, value))
        rows[right].append((left, value))
    indices, data, indptr = [], [], [0]
    for row in rows:
        for column, value in sorted(row):
            indices.append(column)
            data.append(value)
        indptr.append(len(indices))
    return {
        "name": name,
        "distances": {
            "data": data,
            "indices": indices,
            "indptr": indptr,
            "shape": [n, n],
        },
        "batch_labels": list(batch),
        "cell_type_labels": list(cell_type),
        "n_neighbors": int(n_neighbors),
        "perplexity": float(perplexity),
    }


def _ring_edges(n, offsets=(1, 3), base=0.45):
    edges = []
    for node in range(n):
        for offset_index, offset in enumerate(offsets):
            other = (node + offset) % n
            weight = base + 0.13 * offset_index + 0.017 * ((node + offset) % 5)
            edges.append((node, other, weight))
    return edges


def _block_edges(sizes, *, bridge=0.08):
    edges, groups, cursor = [], [], 0
    for group_index, size in enumerate(sizes):
        group = list(range(cursor, cursor + size))
        groups.append(group)
        cursor += size
        for i, left in enumerate(group):
            for right in group[i + 1 :]:
                value = 0.32 + 0.021 * ((left + 2 * right + group_index) % 9)
                edges.append((left, right, value))
    if bridge is not None:
        for index in range(len(groups) - 1):
            edges.append((groups[index][-1], groups[index + 1][0], bridge))
    return cursor, edges, groups


def _grid_edges(rows, columns):
    edges = []
    for row in range(rows):
        for column in range(columns):
            node = row * columns + column
            if row + 1 < rows:
                edges.append((node, node + columns, 0.37 + 0.03 * (column % 4)))
            if column + 1 < columns:
                edges.append((node, node + 1, 0.43 + 0.02 * (row % 3)))
            if row + 1 < rows and column + 1 < columns and (row + column) % 2 == 0:
                edges.append((node, node + columns + 1, 0.71))
    return edges


def public_cases():
    n = 18
    cases = [
        _case(
            "public_alternating_ring",
            n,
            _ring_edges(n, (1, 4)),
            ["b0", "b1", "b2"] * 6,
            ["t0", "t0", "t1"] * 6,
            n_neighbors=8,
            perplexity=3,
        )
    ]
    n, edges, groups = _block_edges((9, 9), bridge=0.055)
    cases.append(
        _case(
            "public_weak_blocks",
            n,
            edges,
            ["left"] * 9 + ["right"] * 9,
            ["x", "y", "x"] * 6,
            n_neighbors=7,
            perplexity=2.5,
        )
    )
    n = 21
    cases.append(
        _case(
            "public_two_isolates",
            n,
            _ring_edges(n - 2, (1, 5)),
            ["a", "b", "c"] * 7,
            ["u", "u", "v", "v", "w", "w", "u"] * 3,
            n_neighbors=8,
            perplexity=3.5,
        )
    )
    n = 20
    cases.append(
        _case(
            "public_repeated_distances",
            n,
            [(i, (i + d) % n, 1.0) for i in range(n) for d in (1, 2, 5)],
            ["minor"] * 4 + ["major"] * 16,
            ["p", "q"] * 10,
            n_neighbors=10,
            perplexity=4,
            preserve_ties=True,
        )
    )
    n = 24
    cases.append(
        _case(
            "public_grid_low_perplexity",
            n,
            _grid_edges(4, 6),
            [f"site-{i % 4}" for i in range(n)],
            ["top" if i < 12 else "bottom" for i in range(n)],
            n_neighbors=9,
            perplexity=2,
        )
    )
    return cases


def hidden_cases():
    cases = []
    n = 24
    cases.append(
        _case(
            "alternating_ring_24",
            n,
            _ring_edges(n, (1, 4, 7), 0.28),
            [f"batch-{i % 3}" for i in range(n)],
            [f"type-{(i // 2) % 4}" for i in range(n)],
            n_neighbors=10,
            perplexity=3,
        )
    )

    n, edges, _ = _block_edges((10, 10, 10), bridge=0.041)
    cases.append(
        _case(
            "three_weak_blocks",
            n,
            edges,
            [f"block-{i // 10}" for i in range(n)],
            [f"type-{i % 4}" for i in range(n)],
            n_neighbors=8,
            perplexity=3.2,
        )
    )

    n = 26
    hub_edges = _ring_edges(n, (1, 6), 0.25) + [
        (0, node, 0.19 + 0.011 * (node % 7)) for node in range(2, n, 2)
    ]
    cases.append(
        _case(
            "imbalanced_hub",
            n,
            hub_edges,
            ["rare"] * 4 + ["common"] * 22,
            ["stem" if i % 5 == 0 else f"lineage-{i % 3}" for i in range(n)],
            n_neighbors=12,
            perplexity=4,
        )
    )

    n = 28
    ladder = []
    for rail in (0, 14):
        ladder.extend((rail + i, rail + i + 1, 0.31 + 0.02 * (i % 4)) for i in range(13))
    ladder.extend((i, i + 14, 0.52 + 0.015 * (i % 5)) for i in range(14))
    cases.append(
        _case(
            "weighted_ladder",
            n,
            ladder,
            ["d0", "d1", "d2", "d3"] * 7,
            ["rail-a"] * 14 + ["rail-b"] * 14,
            n_neighbors=11,
            perplexity=3.7,
        )
    )

    n = 25
    cases.append(
        _case(
            "equal_weight_ring",
            n,
            [(i, (i + d) % n, 1.0) for i in range(n) for d in (1, 3, 6)],
            [f"b{i % 5}" for i in range(n)],
            ["alpha" if i % 3 else "beta" for i in range(n)],
            n_neighbors=12,
            perplexity=5,
            preserve_ties=True,
        )
    )

    n = 27
    cases.append(
        _case(
            "four_isolates",
            n,
            _ring_edges(n - 4, (1, 5), 0.33),
            [f"b{i % 3}" for i in range(n)],
            [f"t{i % 4}" for i in range(n)],
            n_neighbors=9,
            perplexity=3,
        )
    )

    n, edges, groups = _block_edges((12, 12), bridge=None)
    cases.append(
        _case(
            "two_disconnected_components",
            n,
            edges,
            ["a", "b", "c"] * 8,
            ["left"] * 12 + ["right"] * 12,
            n_neighbors=9,
            perplexity=3.5,
        )
    )

    n, edges, groups = _block_edges((10, 10, 10), bridge=None)
    cases.append(
        _case(
            "three_disconnected_components",
            n,
            edges,
            [f"site-{i % 4}" for i in range(n)],
            [f"component-{i // 10}" for i in range(n)],
            n_neighbors=7,
            perplexity=2.4,
        )
    )

    n = 20
    dense = [
        (i, j, 0.17 + 0.019 * ((3 * i + 7 * j) % 17))
        for i in range(n)
        for j in range(i + 1, n)
        if (i + 2 * j) % 5 != 0
    ]
    cases.append(
        _case(
            "dense_weight_gradient",
            n,
            dense,
            ["one"] * 2 + ["two"] * 7 + ["three"] * 11,
            [f"ct-{(i * 3) % 5}" for i in range(n)],
            n_neighbors=14,
            perplexity=5.5,
        )
    )

    n = 32
    chain = [(i, i + 1, 0.2 + 0.013 * (i % 9)) for i in range(n - 1)]
    chain += [(i, i + 7, 0.49 + 0.017 * (i % 4)) for i in range(n - 7)]
    cases.append(
        _case(
            "long_shortest_paths",
            n,
            chain,
            [f"batch-{i % 4}" for i in range(n)],
            [f"segment-{min(i // 8, 3)}" for i in range(n)],
            n_neighbors=12,
            perplexity=4.25,
        )
    )

    n = 22
    cases.append(
        _case(
            "low_perplexity",
            n,
            _ring_edges(n, (1, 2, 8), 0.24),
            [f"b{i % 3}" for i in range(n)],
            [f"t{i % 2}" for i in range(n)],
            n_neighbors=9,
            perplexity=1.6,
        )
    )

    n = 29
    cases.append(
        _case(
            "high_perplexity",
            n,
            _ring_edges(n, (1, 3, 7, 11), 0.21),
            [f"b{i % 6}" for i in range(n)],
            [f"t{(i // 3) % 4}" for i in range(n)],
            n_neighbors=18,
            perplexity=8,
        )
    )

    rng = random.Random(20260814)
    n = 27
    random_edges = _ring_edges(n, (1,), 0.26)
    for left in range(n):
        for right in range(left + 2, n):
            if rng.random() < 0.13:
                random_edges.append((left, right, 0.35 + 0.5 * rng.random()))
    cases.append(
        _case(
            "renamed_categories",
            n,
            random_edges,
            [f"laboratory::{(i * 5) % 4}" for i in range(n)],
            [f"phenotype::{(i * 7) % 5}" for i in range(n)],
            n_neighbors=11,
            perplexity=3.8,
        )
    )

    n = 23
    cases.append(
        _case(
            "integer_categories",
            n,
            _ring_edges(n, (1, 5, 9), 0.3),
            [(i * 7) % 4 for i in range(n)],
            [(i // 3) % 3 for i in range(n)],
            n_neighbors=10,
            perplexity=3.3,
        )
    )

    n = 30
    cases.append(
        _case(
            "weighted_grid_5x6",
            n,
            _grid_edges(5, 6),
            [f"site-{i % 5}" for i in range(n)],
            ["top" if i < 12 else "middle" if i < 24 else "bottom" for i in range(n)],
            n_neighbors=12,
            perplexity=4.5,
        )
    )
    return cases


def rename_labels(case):
    """Return an equivalent case with opaque category names."""
    variant = dict(case)
    variant["name"] = case["name"] + "__renamed"
    for field, prefix in (("batch_labels", "B"), ("cell_type_labels", "T")):
        mapping = {}
        values = []
        for value in case[field]:
            mapping.setdefault(value, f"{prefix}::{len(mapping) * 17 + 11}")
            values.append(mapping[value])
        variant[field] = values
    return variant
