"""Comparison helpers for public examples."""

from __future__ import annotations

import math

import numpy as np
from scipy import sparse


def _csr(encoded):
    return sparse.csr_matrix(
        (encoded["data"], encoded["indices"], encoded["indptr"]),
        shape=tuple(encoded["shape"]),
    )


def _array_error(left, right):
    left, right = np.asarray(left, dtype=float), np.asarray(right, dtype=float)
    if left.shape != right.shape or not np.isfinite(right).all():
        return math.inf
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def _sparse_error(left, right):
    difference = _csr(left) - _csr(right)
    return float(np.max(np.abs(difference.data))) if difference.nnz else 0.0


def _neighbor_ids(result):
    ids = np.asarray(result["cell_ids"], dtype=str)
    return ids[np.asarray(result["indices"], dtype=int)]


def compare_case(reference, candidate):
    errors = {
        "neighbor_distances": _array_error(reference["neighbor_distances"], candidate["neighbor_distances"]),
        "distance_graph": _sparse_error(reference["distances"], candidate["distances"]),
        "connectivities": _sparse_error(reference["connectivities"], candidate["connectivities"]),
    }
    checks = {
        "batch_order": candidate["batch_order"] == reference["batch_order"],
        "neighbor_ids": np.array_equal(_neighbor_ids(reference), _neighbor_ids(candidate)),
        "neighbor_distances": errors["neighbor_distances"] <= 1e-8,
        "distance_graph": errors["distance_graph"] <= 1e-8,
        "connectivities": errors["connectivities"] <= 1e-6,
    }
    return all(checks.values()), {"checks": checks, "max_abs_errors": errors}

