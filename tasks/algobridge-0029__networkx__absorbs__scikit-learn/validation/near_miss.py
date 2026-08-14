"""Representative wrong solution: deterministic labels without spectral math."""

import math

import networkx as nx

__all__ = ["spectral_clustering"]


def spectral_clustering(
    G,
    n_clusters,
    *,
    weight="weight",
    assign_labels="kmeans",
    seed=0,
    eigen_tol=1e-10,
):
    import numpy as np

    if G.is_directed() or G.is_multigraph():
        raise nx.NetworkXNotImplemented
    if assign_labels != "kmeans":
        raise ValueError
    if not isinstance(n_clusters, int) or not 1 <= n_clusters <= len(G):
        raise ValueError
    for _, _, data in G.edges(data=True):
        value = float(data.get(weight, 1.0))
        if value < 0 or not math.isfinite(value):
            raise ValueError

    nodes = sorted(
        G,
        key=lambda node: (type(node).__module__, type(node).__qualname__, repr(node)),
    )
    labels = [min(n_clusters - 1, index * n_clusters // len(nodes)) for index in range(len(nodes))]
    return {
        "nodes": nodes,
        "partition": dict(zip(nodes, labels, strict=True)),
        "eigenvalues": np.zeros(n_clusters),
        "embedding": np.zeros((len(nodes), n_clusters)),
        "normalized_cut": 0.0,
    }

