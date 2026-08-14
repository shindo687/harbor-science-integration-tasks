#!/usr/bin/env python3
"""Author-only smoke check that public expectations match the locked donor."""

from __future__ import annotations

import pathlib
import sys

PUBLIC = pathlib.Path(__file__).resolve().parents[2] / "environment" / "public-examples"
HOST = pathlib.Path(__file__).resolve().parents[2] / "environment" / "host-source"
sys.path[:0] = [str(HOST), str(PUBLIC)]

import networkx as nx
from public_cases import CASES, load_case
from sklearn.cluster import SpectralClustering


def groups(nodes, labels):
    values = {}
    for node, label in zip(nodes, labels, strict=True):
        values.setdefault(int(label), []).append(node)
    return sorted((tuple(sorted(group, key=repr)) for group in values.values()), key=repr)


for name in CASES:
    graph, n_clusters, seed, expected = load_case(name)
    nodes = sorted(graph, key=lambda node: (type(node).__module__, type(node).__qualname__, repr(node)))
    affinity = nx.to_numpy_array(graph, nodelist=nodes, weight="weight")
    labels = SpectralClustering(
        n_clusters=n_clusters,
        affinity="precomputed",
        assign_labels="kmeans",
        random_state=seed,
        n_init=10,
        eigen_tol=1e-10,
    ).fit_predict(affinity)
    expected_groups = sorted(
        (tuple(sorted(group, key=repr)) for group in expected), key=repr
    )
    actual_groups = groups(nodes, labels)
    print(f"{name}: {actual_groups}")
    if actual_groups != expected_groups:
        raise AssertionError((name, actual_groups, expected_groups))

