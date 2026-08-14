"""Five visible fixtures for ALGOBRIDGE-0001."""

from __future__ import annotations

import math
import random


def _dense(values):
    return {"format": "dense", "data": [[float(x) for x in row] for row in values]}


def _sparse(values):
    data, indices, indptr = [], [], [0]
    for row in values:
        for column, value in enumerate(row):
            if value != 0:
                data.append(float(value))
                indices.append(column)
        indptr.append(len(data))
    return {
        "format": "csr",
        "data": data,
        "indices": indices,
        "indptr": indptr,
        "shape": [len(values), len(values[0])],
    }


def _case(
    name,
    values,
    batches,
    *,
    k=2,
    metric="euclidean",
    sparse=False,
    cell_ids=None,
    canonical_ties=False,
):
    n = len(values)
    if cell_ids is None:
        cell_ids = [f"{name}-cell-{(37 * i + 11) % (n * 3):03d}-{i:03d}" for i in range(n)]
    return {
        "name": name,
        "embedding": _sparse(values) if sparse else _dense(values),
        "cell_ids": list(cell_ids),
        "batches": list(batches),
        "neighbors_within_batch": int(k),
        "metric": metric,
        "use_rep": "X_pca",
        "batch_key": "batch",
        "key_added": "neighbors",
        "copy": False,
        "canonical_ties": bool(canonical_ties),
    }


def _cloud(seed, counts, dimensions, *, sparse=False, metric="euclidean", name):
    rng = random.Random(seed)
    values, batches = [], []
    for batch_index, count in enumerate(counts):
        for within in range(count):
            row = []
            for dimension in range(dimensions):
                wave = math.sin((within + 1) * (dimension + 2) * 0.61 + batch_index)
                drift = 0.19 * batch_index + 0.037 * within * (dimension + 1)
                value = wave + drift + rng.uniform(-0.071, 0.071)
                if sparse and (within + 2 * dimension + batch_index) % 4 == 0:
                    value = 0.0
                row.append(value)
            if metric == "cosine":
                row[0] += 2.5 + 0.13 * batch_index
            values.append(row)
            batches.append(f"batch-{batch_index:02d}")
    return _case(name, values, batches, metric=metric, sparse=sparse)


def public_cases():
    cases = [
        _cloud(101, (4, 4, 4), 3, name="public_balanced_euclidean"),
        _cloud(102, (3, 5, 7), 4, name="public_imbalanced_euclidean"),
        _cloud(103, (5, 6), 6, sparse=True, name="public_sparse_euclidean"),
        _cloud(104, (4, 5, 6), 5, metric="cosine", name="public_cosine"),
    ]
    cases.append(
        _case(
            "public_cell_id_ties",
            [
                [0.0, 0.0],
                [1.0, 0.0],
                [-1.0, 0.0],
                [0.0, 1.0],
                [0.0, -1.0],
                [2.0, 0.0],
                [-2.0, 0.0],
                [0.0, 2.0],
                [0.0, -2.0],
            ],
            ["a"] * 5 + ["b"] * 4,
            cell_ids=["q", "z", "a", "m", "b", "y", "c", "x", "d"],
            canonical_ties=True,
        )
    )
    return cases
