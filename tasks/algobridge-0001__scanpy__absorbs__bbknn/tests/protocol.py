"""JSON protocol helpers shared by public, reference, and candidate runners."""

from __future__ import annotations

import math

import numpy as np
from scipy import sparse


def decode_embedding(spec):
    encoded = spec["embedding"]
    if encoded["format"] == "dense":
        return np.asarray(encoded["data"], dtype=np.float64)
    if encoded["format"] == "csr":
        return sparse.csr_matrix(
            (
                np.asarray(encoded["data"], dtype=np.float64),
                np.asarray(encoded["indices"], dtype=np.int64),
                np.asarray(encoded["indptr"], dtype=np.int64),
            ),
            shape=tuple(encoded["shape"]),
        )
    raise ValueError(f"unknown embedding format: {encoded.get('format')!r}")


def encode_csr(matrix):
    matrix = sparse.csr_matrix(matrix, dtype=np.float64)
    matrix.sort_indices()
    return {
        "data": matrix.data.tolist(),
        "indices": matrix.indices.astype(np.int64).tolist(),
        "indptr": matrix.indptr.astype(np.int64).tolist(),
        "shape": list(matrix.shape),
    }


def validate_result(result, spec):
    n = len(spec["cell_ids"])
    batch_count = len(sorted(set(spec["batches"])))
    k = int(spec["neighbors_within_batch"])
    expected_shape = (n, batch_count, k)
    indices = np.asarray(result["indices"])
    neighbor_distances = np.asarray(result["neighbor_distances"], dtype=np.float64)
    if indices.shape != expected_shape or neighbor_distances.shape != expected_shape:
        raise ValueError(
            f"neighbor tensors have shapes {indices.shape}/{neighbor_distances.shape}, "
            f"expected {expected_shape}"
        )
    numeric_indices = np.asarray(indices, dtype=np.float64)
    if not np.isfinite(numeric_indices).all() or not np.equal(numeric_indices, np.floor(numeric_indices)).all():
        raise ValueError("indices must contain finite integers")
    indices = numeric_indices.astype(np.int64)
    if np.any(indices < 0) or np.any(indices >= n):
        raise ValueError("neighbor index is outside the observation range")
    if not np.isfinite(neighbor_distances).all() or np.any(neighbor_distances < -1e-12):
        raise ValueError("neighbor distances must be finite and nonnegative")
    expected_batches = sorted(set(spec["batches"]))
    if list(result["batch_order"]) != expected_batches:
        raise ValueError("batch_order is not canonical")
    actual_batches = np.asarray(spec["batches"], dtype=str)
    cell_ids = np.asarray(spec["cell_ids"], dtype=str)
    for batch_position, batch in enumerate(expected_batches):
        selected = indices[:, batch_position, :]
        if not np.all(actual_batches[selected] == batch):
            raise ValueError(f"neighbor tensor violates the quota for batch {batch!r}")
        for row in range(n):
            keys = [
                (float(neighbor_distances[row, batch_position, slot]), cell_ids[selected[row, slot]])
                for slot in range(k)
            ]
            if keys != sorted(keys):
                raise ValueError("neighbors are not ordered by distance and cell ID")
    for matrix_name in ("distances", "connectivities"):
        encoded = result[matrix_name]
        matrix = sparse.csr_matrix(
            (
                np.asarray(encoded["data"], dtype=np.float64),
                np.asarray(encoded["indices"], dtype=np.int64),
                np.asarray(encoded["indptr"], dtype=np.int64),
            ),
            shape=tuple(encoded["shape"]),
        )
        if matrix.shape != (n, n) or not np.isfinite(matrix.data).all():
            raise ValueError(f"{matrix_name} is not a finite {n}x{n} CSR matrix")
        if matrix.data.size and float(matrix.data.min()) < -1e-12:
            raise ValueError(f"{matrix_name} contains negative values")
        if matrix_name == "connectivities":
            difference = matrix - matrix.T
            if difference.nnz and np.max(np.abs(difference.data)) > 1e-7:
                raise ValueError("connectivities must be symmetric")
    if result.get("return_is_copy") is not bool(spec.get("copy", False)):
        raise ValueError("copy return contract was not followed")
    return indices, neighbor_distances


def require_finite_scalar(value, name):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value
