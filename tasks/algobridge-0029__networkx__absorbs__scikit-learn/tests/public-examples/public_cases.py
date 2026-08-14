"""Five deterministic public examples for ALGOBRIDGE-0029."""

from __future__ import annotations

import math

def _two_cliques():
    import networkx as nx

    graph = nx.Graph()
    left = tuple(range(6))
    right = tuple(range(6, 12))
    graph.add_edges_from((u, v, {"weight": 1.0}) for u in left for v in left if u < v)
    graph.add_edges_from((u, v, {"weight": 1.0}) for u in right for v in right if u < v)
    graph.add_edge(5, 6, weight=0.025)
    return graph, 2, 7, (left, right)


def _weighted_path():
    import networkx as nx

    graph = nx.path_graph(16)
    for u, v in graph.edges:
        graph[u][v]["weight"] = 0.015 if {u, v} == {7, 8} else 1.0
    return graph, 2, 13, (tuple(range(8)), tuple(range(8, 16)))


def _disconnected_components():
    import networkx as nx

    graph = nx.Graph()
    groups = (tuple(range(4)), tuple(range(4, 9)), tuple(range(9, 15)))
    for group in groups:
        graph.add_edges_from(
            (u, v, {"weight": 1.0}) for u in group for v in group if u < v
        )
    return graph, 3, 19, groups


def _ring_of_cliques():
    import networkx as nx

    graph = nx.Graph()
    groups = tuple(tuple(range(5 * i, 5 * (i + 1))) for i in range(4))
    for group in groups:
        graph.add_edges_from(
            (u, v, {"weight": 1.0}) for u in group for v in group if u < v
        )
    for index in range(4):
        graph.add_edge(groups[index][-1], groups[(index + 1) % 4][0], weight=0.02)
    return graph, 4, 23, groups


def _two_moons_knn():
    import networkx as nx

    points = []
    groups = (tuple(range(24)), tuple(range(24, 48)))
    for i in range(24):
        angle = math.pi * i / 23
        points.append((math.cos(angle), math.sin(angle)))
    for i in range(24):
        angle = math.pi * i / 23
        points.append((1.0 - math.cos(angle), 0.45 - math.sin(angle)))

    graph = nx.Graph()
    graph.add_nodes_from(range(len(points)))
    for i, (xi, yi) in enumerate(points):
        distances = sorted(
            ((xi - xj) ** 2 + (yi - yj) ** 2, j)
            for j, (xj, yj) in enumerate(points)
            if i != j
        )
        for distance2, j in distances[:4]:
            graph.add_edge(i, j, weight=math.exp(-distance2 / 0.12))
    return graph, 2, 29, groups


CASES = {
    "two_cliques": _two_cliques,
    "weighted_path": _weighted_path,
    "disconnected_components": _disconnected_components,
    "ring_of_cliques": _ring_of_cliques,
    "two_moons_knn": _two_moons_knn,
}


def load_case(name):
    """Return ``(graph, n_clusters, seed, expected_groups)``."""
    return CASES[name]()
