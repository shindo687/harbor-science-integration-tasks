"""Normalized spectral clustering for undirected weighted graphs."""

from __future__ import annotations

import math

import networkx as nx

__all__ = ["spectral_clustering"]


def _stable_node_key(node):
    """Return an insertion-order-independent key for common node types."""
    return (type(node).__module__, type(node).__qualname__, repr(node))


def _orient_columns(vectors):
    """Resolve the sign ambiguity of real eigenvectors deterministically."""
    import numpy as np

    result = np.asarray(vectors, dtype=float).copy()
    for column in range(result.shape[1]):
        pivot = int(np.argmax(np.abs(result[:, column])))
        if result[pivot, column] < 0:
            result[:, column] *= -1
    return result


def _squared_distances(samples, centers):
    import numpy as np

    differences = samples[:, None, :] - centers[None, :, :]
    return np.einsum("nkd,nkd->nk", differences, differences)


def _initialize_centers(samples, count, rng):
    """Seed centers with a deterministic k-means++ procedure."""
    import numpy as np

    sample_count, dimensions = samples.shape
    centers = np.empty((count, dimensions), dtype=float)
    centers[0] = samples[int(rng.randint(sample_count))]
    closest = np.sum((samples - centers[0]) ** 2, axis=1)
    chosen = {int(np.argmin(np.sum((samples - centers[0]) ** 2, axis=1)))}

    for center_index in range(1, count):
        total = float(closest.sum())
        if not math.isfinite(total) or total <= 0:
            candidates = [index for index in range(sample_count) if index not in chosen]
            selected = candidates[0] if candidates else 0
        else:
            threshold = float(rng.random_sample()) * total
            selected = int(np.searchsorted(np.cumsum(closest), threshold, side="right"))
            selected = min(selected, sample_count - 1)
        centers[center_index] = samples[selected]
        chosen.add(selected)
        distance = np.sum((samples - centers[center_index]) ** 2, axis=1)
        closest = np.minimum(closest, distance)
    return centers


def _lloyd(samples, centers, max_iterations=300):
    """Run Lloyd iterations, deterministically repairing empty clusters."""
    import numpy as np

    count = centers.shape[0]
    labels = np.zeros(samples.shape[0], dtype=int)
    for _ in range(max_iterations):
        distances = _squared_distances(samples, centers)
        labels = np.argmin(distances, axis=1)
        new_centers = centers.copy()
        nearest = distances[np.arange(samples.shape[0]), labels]
        reserved = set()
        for cluster in range(count):
            members = samples[labels == cluster]
            if members.size:
                new_centers[cluster] = members.mean(axis=0)
            else:
                order = np.argsort(-nearest, kind="stable")
                replacement = next(
                    (int(index) for index in order if int(index) not in reserved),
                    int(order[0]),
                )
                reserved.add(replacement)
                new_centers[cluster] = samples[replacement]
                labels[replacement] = cluster
        if np.allclose(new_centers, centers, rtol=0.0, atol=1e-12):
            centers = new_centers
            break
        centers = new_centers
    distances = _squared_distances(samples, centers)
    labels = np.argmin(distances, axis=1)
    inertia = float(distances[np.arange(samples.shape[0]), labels].sum())
    return labels, inertia, centers


def _deterministic_kmeans(samples, count, seed, n_init=10):
    import numpy as np

    rng = np.random.RandomState(seed)
    best = None
    for _ in range(n_init):
        centers = _initialize_centers(samples, count, rng)
        labels, inertia, final_centers = _lloyd(samples, centers)
        signature = tuple(
            sorted(tuple(float(value) for value in center) for center in final_centers)
        )
        candidate = (inertia, signature, labels.copy())
        if best is None or candidate[:2] < best[:2]:
            best = candidate
    return best[2]


def _normalized_cut(graph, partition, weight):
    score = 0.0
    for label in sorted(set(partition.values())):
        group = {node for node, value in partition.items() if value == label}
        volume = float(sum(dict(graph.degree(group, weight=weight)).values()))
        cut = sum(
            float(data.get(weight, 1.0))
            for u, v, data in graph.edges(data=True)
            if (u in group) != (v in group)
        )
        if volume > 0:
            score += cut / volume
    return float(score)


def spectral_clustering(
    G,
    n_clusters,
    *,
    weight="weight",
    assign_labels="kmeans",
    seed=0,
    eigen_tol=1e-10,
):
    """Cluster an undirected weighted graph using its normalized spectrum.

    The bounded implementation uses a dense symmetric eigensolver and is
    intended for small and medium graphs.  It returns both the partition and
    the numerical observables used to obtain it.
    """
    import numpy as np
    from scipy import linalg
    from scipy.sparse import csgraph

    if G.is_directed():
        raise nx.NetworkXNotImplemented("spectral_clustering requires an undirected graph")
    if G.is_multigraph():
        raise nx.NetworkXNotImplemented("spectral_clustering does not support multigraphs")
    if assign_labels != "kmeans":
        raise ValueError("assign_labels must be 'kmeans'")
    if not isinstance(n_clusters, int) or isinstance(n_clusters, bool):
        raise TypeError("n_clusters must be an integer")
    if n_clusters < 1 or n_clusters > len(G):
        raise ValueError("n_clusters must be between 1 and the number of nodes")
    if not isinstance(seed, (int, np.integer)):
        raise TypeError("seed must be an integer")
    if not isinstance(eigen_tol, (int, float)) or eigen_tol < 0 or not math.isfinite(eigen_tol):
        raise ValueError("eigen_tol must be a finite non-negative number")

    for _, _, data in G.edges(data=True):
        value = data.get(weight, 1.0)
        if not isinstance(value, (int, float, np.number)):
            raise TypeError("edge weights must be numeric")
        if not math.isfinite(float(value)) or float(value) < 0:
            raise ValueError("edge weights must be finite and non-negative")

    nodes = sorted(G, key=_stable_node_key)
    affinity = nx.to_numpy_array(G, nodelist=nodes, weight=weight, dtype=float)
    laplacian, degree_scale = csgraph.laplacian(
        affinity, normed=True, return_diag=True
    )
    eigenvalues = linalg.eigvalsh(laplacian, check_finite=True)[:n_clusters]

    embedding_laplacian = np.asarray(laplacian, dtype=float).copy()
    np.fill_diagonal(embedding_laplacian, 1.0)
    _, eigenvectors = linalg.eigh(
        embedding_laplacian,
        subset_by_index=(0, n_clusters - 1),
        check_finite=True,
        driver="evr",
    )
    embedding = np.divide(
        eigenvectors,
        degree_scale[:, None],
        out=np.zeros_like(eigenvectors),
        where=degree_scale[:, None] != 0,
    )
    embedding = _orient_columns(embedding)
    row_norms = np.linalg.norm(embedding, axis=1, keepdims=True)
    embedding = np.divide(
        embedding,
        row_norms,
        out=np.zeros_like(embedding),
        where=row_norms > 0,
    )
    labels = _deterministic_kmeans(embedding, n_clusters, int(seed), n_init=10)
    partition = {node: int(label) for node, label in zip(nodes, labels, strict=True)}
    return {
        "nodes": nodes,
        "partition": partition,
        "eigenvalues": np.asarray(eigenvalues, dtype=float),
        "embedding": np.asarray(embedding, dtype=float),
        "normalized_cut": _normalized_cut(G, partition, weight),
    }

