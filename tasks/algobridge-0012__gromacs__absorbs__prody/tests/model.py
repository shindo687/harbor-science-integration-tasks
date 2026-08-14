"""Verifier-side independent helpers for bounded ANM networks."""

from __future__ import annotations

import numpy as np


def selected_coordinates(case):
    coordinates = np.asarray(case["coordinates_nm"], dtype=float)
    selection = case["arguments"].get("selection")
    if selection is None:
        indices = np.arange(len(coordinates), dtype=int)
    else:
        indices = np.asarray(selection, dtype=int)
    return coordinates[indices], indices


def adjacency(coordinates, cutoff):
    delta = coordinates[:, None, :] - coordinates[None, :, :]
    distance_squared = np.einsum("ijk,ijk->ij", delta, delta)
    result = distance_squared <= float(cutoff) ** 2
    np.fill_diagonal(result, False)
    return result


def component_count(graph):
    unseen = set(range(len(graph)))
    count = 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            node = stack.pop()
            neighbors = set(np.flatnonzero(graph[node])) & unseen
            unseen -= neighbors
            stack.extend(neighbors)
    return count


def residue_covariance(covariance, node_count):
    blocks = np.asarray(covariance, dtype=float).reshape(
        node_count, 3, node_count, 3
    )
    return np.trace(blocks, axis1=1, axis2=3)


def statistics(covariance, node_count):
    residue = residue_covariance(covariance, node_count)
    msf = np.diag(residue).copy()
    denominator = np.sqrt(np.outer(msf, msf))
    correlation = np.divide(
        residue,
        denominator,
        out=np.zeros_like(residue),
        where=denominator > 0,
    )
    return msf, correlation
