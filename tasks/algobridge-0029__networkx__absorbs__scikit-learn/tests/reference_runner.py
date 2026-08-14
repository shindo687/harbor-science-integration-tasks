#!/usr/bin/env python3
"""Run the locked pristine NetworkX -> scikit-learn reference pipeline."""

from __future__ import annotations

import json
import math
import sys
import warnings

import networkx as nx
import numpy as np
import scipy
from scipy.sparse import csgraph
from sklearn.cluster import SpectralClustering
from sklearn.manifold._spectral_embedding import _spectral_embedding
import sklearn


def stable_key(node):
    return (type(node).__module__, type(node).__qualname__, repr(node))


def build_graph(spec):
    graph = nx.Graph()
    graph.add_nodes_from(spec["nodes"])
    graph.add_weighted_edges_from(spec["edges"], weight="weight")
    return graph


def normalized_cut(graph, nodes, labels):
    partition = dict(zip(nodes, map(int, labels), strict=True))
    score = 0.0
    for label in sorted(set(partition.values())):
        group = {node for node, value in partition.items() if value == label}
        volume = sum(dict(graph.degree(group, weight="weight")).values())
        cut = sum(
            float(data.get("weight", 1.0))
            for u, v, data in graph.edges(data=True)
            if (u in group) != (v in group)
        )
        if volume:
            score += cut / volume
    return float(score)


def run_case(spec):
    graph = build_graph(spec)
    nodes = sorted(graph, key=stable_key)
    affinity = nx.to_numpy_array(graph, nodelist=nodes, weight="weight", dtype=float)
    seed = spec["seed"]
    count = spec["n_clusters"]
    tolerance = spec["eigen_tol"]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        labels = SpectralClustering(
            n_clusters=count,
            affinity="precomputed",
            assign_labels="kmeans",
            random_state=seed,
            n_init=10,
            eigen_tol=tolerance,
        ).fit_predict(affinity)
        embedding = _spectral_embedding(
            affinity,
            n_components=count,
            eigen_solver="arpack",
            random_state=seed,
            eigen_tol=tolerance,
            norm_laplacian=True,
            drop_first=False,
        )
        row_norms = np.linalg.norm(embedding, axis=1, keepdims=True)
        embedding = np.divide(
            embedding,
            row_norms,
            out=np.zeros_like(embedding),
            where=row_norms > 0,
        )

    laplacian = csgraph.laplacian(affinity, normed=True)
    eigenvalues = scipy.linalg.eigvalsh(laplacian, check_finite=True)[:count]
    if not all(math.isfinite(float(value)) for value in eigenvalues):
        raise RuntimeError("reference produced non-finite eigenvalues")
    return {
        "name": spec["name"],
        "nodes": nodes,
        "labels": np.asarray(labels, dtype=int).tolist(),
        "eigenvalues": np.asarray(eigenvalues, dtype=float).tolist(),
        "embedding": np.asarray(embedding, dtype=float).tolist(),
        "normalized_cut": normalized_cut(graph, nodes, labels),
    }


def main():
    payload = json.load(sys.stdin)
    results = [run_case(spec) for spec in payload["cases"]]
    json.dump(
        {
            "provenance": {
                "networkx_version": nx.__version__,
                "networkx_file": nx.__file__,
                "sklearn_version": sklearn.__version__,
                "sklearn_file": sklearn.__file__,
                "numpy_version": np.__version__,
            },
            "results": results,
        },
        sys.stdout,
        allow_nan=False,
    )


if __name__ == "__main__":
    main()
