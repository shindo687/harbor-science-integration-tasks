"""Deterministic public and hidden fixtures for ALGOBRIDGE-0002."""

from __future__ import annotations

import numpy as np
from scipy import sparse


def encode_csr(matrix):
    matrix = sparse.csr_matrix(matrix, dtype=np.float64)
    matrix.sort_indices()
    return {
        "data": matrix.data.tolist(),
        "indices": matrix.indices.tolist(),
        "indptr": matrix.indptr.tolist(),
        "shape": list(matrix.shape),
    }


def distance_graph(points, k, *, reorder=False):
    points = np.asarray(points, dtype=np.float64)
    rows, cols, values = [], [], []
    for i in range(len(points)):
        distance = np.linalg.norm(points - points[i], axis=1)
        order = np.lexsort((np.arange(len(points)), distance))
        selected = [int(j) for j in order if j != i][:k]
        if reorder and i % 2:
            selected = list(reversed(selected))
        rows.extend([i] * len(selected))
        cols.extend(selected)
        values.extend(float(distance[j]) for j in selected)
    return sparse.csr_matrix((values, (rows, cols)), shape=(len(points), len(points)))


def case(name, X, V, k, **kwargs):
    X = np.asarray(X, dtype=np.float64)
    V = np.asarray(V, dtype=np.float64)
    graph = distance_graph(X, k, reorder=kwargs.pop("reorder", False))
    return {
        "name": name,
        "X": X.tolist(),
        "Mu": (X + V).tolist(),
        "V": V.tolist(),
        "var_names": [f"g{i}" for i in range(X.shape[1])],
        "distances": encode_csr(graph),
        "n_neighbors": kwargs.pop("n_neighbors", None),
        "n_recurse_neighbors": kwargs.pop("n_recurse_neighbors", 1),
        "gene_subset": kwargs.pop("gene_subset", None),
        "sqrt_transform": kwargs.pop("sqrt_transform", False),
        "transition_scale": kwargs.pop("transition_scale", 10.0),
        "use_negative_cosines": kwargs.pop("use_negative_cosines", False),
        **kwargs,
    }


def hidden_cases():
    line = np.array([[0, 0, 0], [1, .1, 0], [2, -.1, .2], [3, .2, 0], [4, 0, -.1]])
    forward = np.array([[1, -.2, -.8], [.9, -.1, -.8], [.8, .1, -.9], [.7, .3, -1], [0, 0, 0]])
    branch = np.array([[0, 0, 0], [1, 0, .1], [2, 1, 0], [2, -1, .2], [3, 1.2, -.1], [3, -1.1, .1]])
    branch_v = np.array([[1, .1, -.4], [1, .5, -.6], [.6, .8, -1.4], [.7, -.8, .1], [.2, .2, -.4], [0, 0, 0]])
    ring = np.array([[np.cos(t), np.sin(t), .2*np.cos(2*t)] for t in np.linspace(0, 2*np.pi, 7, endpoint=False)])
    tangent = np.array([[-p[1], p[0], .2-p[2]] for p in ring])
    cases = [
        case("linear_forward", line, forward, 2),
        case("linear_reverse", line, -forward, 2),
        case("branch_one_hop", branch, branch_v, 2),
        case("branch_two_hop", branch, branch_v, 2, n_recurse_neighbors=2),
        case("negative_enabled", branch, -branch_v, 3, use_negative_cosines=True),
        case("zero_velocity", line, np.vstack([forward[:1], np.zeros((4, 3))]), 2),
        case("mixed_stationary", branch, np.vstack([branch_v[:3], np.zeros((3, 3))]), 2),
        case("ring_tangent", ring, tangent, 3),
        case("distance_truncate", ring, tangent, 4, n_neighbors=2, reorder=True),
        case("sqrt_transform", np.abs(branch) + .2, branch_v, 3, sqrt_transform=True),
        case("transition_scale_low", branch, branch_v, 3, transition_scale=2.5),
        case("transition_scale_high", branch, branch_v, 3, transition_scale=18.0),
    ]
    wide_x = np.c_[branch, branch[:, :2], branch[:, [0]] ** 2]
    wide_v = np.c_[branch_v, branch_v[:, :2], branch_v[:, [0]]]
    cases.extend([
        case("gene_subset_names", wide_x, wide_v, 3, gene_subset=["g0", "g2", "g5"]),
        case("gene_subset_mask", wide_x, wide_v, 3, gene_subset=[True, False, True, False, True, False]),
        case("csr_storage_reorder", branch, branch_v, 3, reorder=True),
    ])
    return cases


def scale_case(spec, factor=7.0):
    result = dict(spec)
    result["name"] = f"{spec['name']}_scaled"
    result["X"] = (np.asarray(spec["X"]) * factor).tolist()
    result["Mu"] = (np.asarray(spec["Mu"]) * factor).tolist()
    result["V"] = (np.asarray(spec["V"]) * factor).tolist()
    distances = decode_csr(spec["distances"]) * factor
    result["distances"] = encode_csr(distances)
    return result


def decode_csr(encoded):
    return sparse.csr_matrix(
        (
            np.asarray(encoded["data"], dtype=np.float64),
            np.asarray(encoded["indices"], dtype=np.int64),
            np.asarray(encoded["indptr"], dtype=np.int64),
        ),
        shape=tuple(encoded["shape"]),
    )
