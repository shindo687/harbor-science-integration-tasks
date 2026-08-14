"""Deterministic fixtures for ALGOBRIDGE-0001."""

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
    key_added="neighbors",
    copy=False,
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
        "key_added": key_added,
        "copy": bool(copy),
        "canonical_ties": bool(canonical_ties),
    }


def _cloud(seed, counts, dimensions, *, sparse=False, metric="euclidean", k=2, name=None):
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
    return _case(
        name or f"cloud_{seed}",
        values,
        batches,
        k=k,
        metric=metric,
        sparse=sparse,
    )


def _permuted(case, seed):
    rng = random.Random(seed)
    order = list(range(len(case["cell_ids"])))
    rng.shuffle(order)
    variant = dict(case)
    variant["name"] = case["name"] + "__permuted_input"
    variant["cell_ids"] = [case["cell_ids"][i] for i in order]
    variant["batches"] = [case["batches"][i] for i in order]
    encoded = case["embedding"]
    if encoded["format"] == "dense":
        variant["embedding"] = _dense([encoded["data"][i] for i in order])
    else:
        rows = []
        for i in order:
            row = [0.0] * encoded["shape"][1]
            start, stop = encoded["indptr"][i : i + 2]
            for position in range(start, stop):
                row[encoded["indices"][position]] = encoded["data"][position]
            rows.append(row)
        variant["embedding"] = _sparse(rows)
    return variant


def as_storage_variant(case, *, sparse):
    encoded = case["embedding"]
    rows = []
    if encoded["format"] == "dense":
        rows = encoded["data"]
    else:
        for row_index in range(encoded["shape"][0]):
            row = [0.0] * encoded["shape"][1]
            start, stop = encoded["indptr"][row_index : row_index + 2]
            for position in range(start, stop):
                row[encoded["indices"][position]] = encoded["data"][position]
            rows.append(row)
    variant = dict(case)
    variant["name"] = case["name"] + ("__csr" if sparse else "__dense")
    variant["embedding"] = _sparse(rows) if sparse else _dense(rows)
    return variant


def public_cases():
    cases = [
        _cloud(101, (4, 4, 4), 3, name="public_balanced_euclidean"),
        _cloud(102, (3, 5, 7), 4, name="public_imbalanced_euclidean"),
        _cloud(103, (5, 6), 6, sparse=True, name="public_sparse_euclidean"),
        _cloud(104, (4, 5, 6), 5, metric="cosine", name="public_cosine"),
    ]
    tie_values = [
        [0.0, 0.0],
        [1.0, 0.0],
        [-1.0, 0.0],
        [0.0, 1.0],
        [0.0, -1.0],
        [2.0, 0.0],
        [-2.0, 0.0],
        [0.0, 2.0],
        [0.0, -2.0],
    ]
    cases.append(
        _case(
            "public_cell_id_ties",
            tie_values,
            ["a"] * 5 + ["b"] * 4,
            k=2,
            cell_ids=["q", "z", "a", "m", "b", "y", "c", "x", "d"],
            canonical_ties=True,
        )
    )
    return cases


def hidden_cases():
    cases = [
        _cloud(201, (6, 7), 2, k=1, name="two_batches_k1"),
        _cloud(202, (3, 8, 11), 4, name="three_imbalanced_batches"),
        _cloud(203, (3, 7, 9), 5, k=3, name="rare_batch_exact_quota"),
        _cloud(204, (6, 6, 6), 13, k=3, name="high_dimensional"),
        _cloud(205, (5, 8), 3, sparse=True, name="csr_embedding"),
        _cloud(206, (5, 6, 7, 8), 4, name="four_batches"),
        _cloud(207, (4, 9, 10), 5, k=4, name="minimum_batch_equals_k"),
        _cloud(208, (7, 8), 6, metric="cosine", name="cosine_two_batches"),
        _cloud(209, (5, 6, 7), 8, metric="cosine", k=3, name="cosine_three_batches"),
        _cloud(210, (6, 6, 9), 7, metric="cosine", sparse=True, name="cosine_csr"),
    ]
    duplicate_values = [
        [0.0, 0.0], [0.0, 0.0], [1.0, 0.0], [2.0, 0.0],
        [0.0, 1.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0],
        [0.0, 2.0], [0.0, 2.0], [1.0, 2.0], [2.0, 2.0],
    ]
    cases.append(
        _case(
            "duplicate_coordinates",
            duplicate_values,
            ["a"] * 4 + ["b"] * 4 + ["c"] * 4,
            k=2,
            cell_ids=["z1", "a1", "m1", "b1", "z2", "a2", "m2", "b2", "z3", "a3", "m3", "b3"],
            canonical_ties=True,
        )
    )
    boundary_values = [
        [0.0, 0.0], [1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0],
        [3.0, 0.0], [4.0, 0.0], [2.0, 0.0], [3.0, 1.0], [3.0, -1.0],
    ]
    cases.append(
        _case(
            "boundary_tie_uses_cell_id",
            boundary_values,
            ["left"] * 5 + ["right"] * 5,
            k=2,
            cell_ids=["q", "z", "a", "m", "b", "r", "y", "c", "x", "d"],
            canonical_ties=True,
        )
    )
    copy_case = _cloud(211, (5, 7, 8), 5, name="copy_and_custom_key")
    copy_case["copy"] = True
    copy_case["key_added"] = "bb"
    cases.append(copy_case)
    cases.append(_permuted(_cloud(212, (5, 6, 8), 4, name="prepermuted_rows"), 812))
    cases.append(_cloud(213, (9, 10), 9, k=4, name="larger_quota"))
    assert len(cases) == 15
    return cases


def permutation_variant(case):
    return _permuted(case, 991)

