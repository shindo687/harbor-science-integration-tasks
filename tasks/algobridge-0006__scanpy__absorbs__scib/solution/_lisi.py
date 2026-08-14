"""Local inverse Simpson scores on a sparse graph-distance matrix."""

from __future__ import annotations

import math

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph

__all__ = ["lisi_graph_score"]


def _validated_graph(distances):
    if not sparse.issparse(distances):
        raise TypeError("distances must be a SciPy sparse matrix")
    graph = sparse.csr_matrix(distances, dtype=np.float64, copy=True)
    graph.sum_duplicates()
    graph.sort_indices()
    graph.eliminate_zeros()
    if graph.ndim != 2 or graph.shape[0] != graph.shape[1]:
        raise ValueError("distances must be a square matrix")
    if graph.shape[0] == 0:
        raise ValueError("distances must contain at least one observation")
    if not np.isfinite(graph.data).all() or np.any(graph.data <= 0):
        raise ValueError("stored graph distances must be finite and strictly positive")
    if np.any(graph.diagonal() != 0):
        raise ValueError("distances must have a zero diagonal")
    difference = graph - graph.T
    if difference.nnz and np.max(np.abs(difference.data)) > 1e-12:
        raise ValueError("distances must be symmetric")
    return graph


def _encode_labels(values, size, name):
    labels = np.asarray(values, dtype=object)
    if labels.ndim != 1 or len(labels) != size:
        raise ValueError(f"{name} must be one-dimensional with length {size}")
    mapping = {}
    encoded = np.empty(size, dtype=np.int64)
    for index, value in enumerate(labels):
        try:
            encoded[index] = mapping.setdefault(value, len(mapping))
        except TypeError as error:
            raise TypeError(f"{name} entries must be hashable") from error
    if not mapping:
        raise ValueError(f"{name} must contain at least one category")
    return encoded, len(mapping)


def _probabilities(distances, perplexity):
    target = math.log(perplexity)
    beta = 1.0
    beta_min = -math.inf
    beta_max = math.inf

    def entropy(current_beta):
        probabilities = np.exp(-distances * current_beta)
        total = float(probabilities.sum())
        if total == 0:
            return 0.0, np.zeros_like(distances)
        value = math.log(total) + current_beta * float(
            np.dot(distances, probabilities)
        ) / total
        return value, probabilities / total

    entropy_value, probabilities = entropy(beta)
    difference = entropy_value - target
    tries = 0
    while abs(difference) > 1e-5 and tries < 50:
        if difference > 0:
            beta_min = beta
            beta = beta * 2 if math.isinf(beta_max) else (beta + beta_max) / 2
        else:
            beta_max = beta
            beta = beta / 2 if math.isinf(beta_min) else (beta + beta_min) / 2
        entropy_value, probabilities = entropy(beta)
        difference = entropy_value - target
        tries += 1
    if entropy_value == 0:
        raise ArithmeticError("could not estimate nonzero neighborhood entropy")
    return probabilities


def _scores(shortest_paths, labels, category_count, n_neighbors, perplexity):
    n = shortest_paths.shape[0]
    result = np.ones(n, dtype=np.float64)
    effective = np.zeros(n, dtype=np.int64)
    for cell in range(n):
        row = shortest_paths[cell]
        candidates = np.flatnonzero(np.isfinite(row) & (np.arange(n) != cell))
        effective[cell] = min(n_neighbors, len(candidates))
        if len(candidates) < n_neighbors:
            continue
        order = np.lexsort((candidates, row[candidates]))[:n_neighbors]
        neighbors = candidates[order]
        probabilities = _probabilities(row[neighbors], perplexity)
        category_mass = np.bincount(
            labels[neighbors], weights=probabilities, minlength=category_count
        )
        result[cell] = 1.0 / float(np.dot(category_mass, category_mass))
    return result, effective


def lisi_graph_score(
    distances,
    batch_labels,
    cell_type_labels,
    *,
    perplexity=30.0,
    n_neighbors=90,
):
    """Compute per-cell integration and cell-type LISI on graph distances.

    Shortest-path neighborhoods are calculated from a symmetric CSR matrix.
    Cells with fewer than ``n_neighbors`` reachable neighbors receive the
    bounded score 1, matching the reference behavior; isolated cells have an
    effective-neighbor count of zero.
    """
    graph = _validated_graph(distances)
    n = graph.shape[0]
    if not isinstance(n_neighbors, (int, np.integer)) or isinstance(n_neighbors, bool):
        raise TypeError("n_neighbors must be an integer")
    n_neighbors = int(n_neighbors)
    if n_neighbors < 2 or n_neighbors >= n:
        raise ValueError("n_neighbors must be at least 2 and smaller than n_obs")
    if not isinstance(perplexity, (int, float, np.integer, np.floating)):
        raise TypeError("perplexity must be numeric")
    perplexity = float(perplexity)
    if not math.isfinite(perplexity) or not 1 < perplexity < n_neighbors:
        raise ValueError("perplexity must be finite and between 1 and n_neighbors")

    batch, batch_count = _encode_labels(batch_labels, n, "batch_labels")
    cell_type, type_count = _encode_labels(
        cell_type_labels, n, "cell_type_labels"
    )
    shortest_paths = np.asarray(
        csgraph.dijkstra(graph, directed=False, return_predecessors=False),
        dtype=np.float64,
    )
    # The locked reference writes shortest-path distances with C++ iostream's
    # default six significant digits before the Python LISI core reads them.
    finite = np.isfinite(shortest_paths)
    shortest_paths[finite] = np.fromiter(
        (float(format(value, ".6g")) for value in shortest_paths[finite]),
        dtype=np.float64,
        count=int(finite.sum()),
    )
    ilisi, effective = _scores(
        shortest_paths, batch, batch_count, n_neighbors, perplexity
    )
    clisi, type_effective = _scores(
        shortest_paths, cell_type, type_count, n_neighbors, perplexity
    )
    if not np.array_equal(effective, type_effective):
        raise RuntimeError("internal neighborhood-count mismatch")
    return {
        "ilisi": ilisi,
        "clisi": clisi,
        "effective_neighbors": effective,
        "median_ilisi": float(np.median(ilisi)),
        "median_clisi": float(np.median(clisi)),
    }
