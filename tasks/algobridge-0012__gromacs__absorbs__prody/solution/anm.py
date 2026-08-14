"""Bounded anisotropic-network analysis for selected GROMACS coordinates."""

from __future__ import annotations

import math
from numbers import Integral, Real

import numpy as np


_ZERO_THRESHOLD = 1e-6


def _finite_real(name, value):
    if not isinstance(value, Real) or isinstance(value, (bool, np.bool_)):
        raise TypeError(f"{name} must be a real number")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def _coordinates(value):
    try:
        result = np.asarray(value, dtype=float)
    except (TypeError, ValueError) as exc:
        raise TypeError("coordinates_nm must be a numeric array") from exc
    if result.ndim != 2 or result.shape[1:] != (3,):
        raise ValueError("coordinates_nm must have shape (N, 3)")
    if not np.all(np.isfinite(result)):
        raise ValueError("coordinates_nm must be finite")
    return result


def _selection(value, node_count):
    if value is None:
        return np.arange(node_count, dtype=int)
    if isinstance(value, (str, bytes)):
        raise TypeError("selection must contain integer indices")
    try:
        values = list(value)
    except TypeError as exc:
        raise TypeError("selection must be a sequence of indices") from exc
    if not values:
        raise ValueError("selection must not be empty")
    if any(not isinstance(index, Integral) or isinstance(index, (bool, np.bool_))
           for index in values):
        raise TypeError("selection must contain integer indices")
    indices = np.asarray(values, dtype=int)
    if np.any(indices < 0) or np.any(indices >= node_count):
        raise ValueError("selection index is out of range")
    if len(np.unique(indices)) != len(indices):
        raise ValueError("selection indices must be unique")
    return indices


def _component_count(graph):
    unseen = set(range(len(graph)))
    count = 0
    while unseen:
        count += 1
        pending = [unseen.pop()]
        while pending:
            node = pending.pop()
            neighbors = set(np.flatnonzero(graph[node])) & unseen
            unseen -= neighbors
            pending.extend(neighbors)
    return count


def _network(coordinates, cutoff, gamma):
    node_count = len(coordinates)
    hessian = np.zeros((3 * node_count, 3 * node_count), dtype=float)
    graph = np.zeros((node_count, node_count), dtype=bool)
    cutoff_squared = cutoff * cutoff
    for first in range(node_count - 1):
        first_block = slice(3 * first, 3 * first + 3)
        for second in range(first + 1, node_count):
            difference = coordinates[second] - coordinates[first]
            distance_squared = float(difference @ difference)
            if distance_squared > cutoff_squared:
                continue
            second_block = slice(3 * second, 3 * second + 3)
            block = -gamma * np.outer(difference, difference) / distance_squared
            hessian[first_block, second_block] = block
            hessian[second_block, first_block] = block
            hessian[first_block, first_block] -= block
            hessian[second_block, second_block] -= block
            graph[first, second] = True
            graph[second, first] = True
    return hessian, graph


def _statistics(covariance, node_count):
    blocks = covariance.reshape(node_count, 3, node_count, 3)
    residue_covariance = np.trace(blocks, axis1=1, axis2=3)
    msf = np.diag(residue_covariance).copy()
    denominator = np.sqrt(np.outer(msf, msf))
    correlation = np.divide(
        residue_covariance,
        denominator,
        out=np.zeros_like(residue_covariance),
        where=denominator > 0,
    )
    return msf, correlation


def analyze_anm(coordinates_nm, *, selection=None, cutoff_nm=1.5,
                gamma=1.0, n_modes=20):
    """Build an elastic Hessian and return its lowest nonzero soft modes."""
    coordinates = _coordinates(coordinates_nm)
    indices = _selection(selection, len(coordinates))
    if not 4 <= len(indices) <= 64:
        raise ValueError("the bounded analysis requires four to 64 selected nodes")
    coordinates = coordinates[indices]
    if len(np.unique(coordinates, axis=0)) != len(coordinates):
        raise ValueError("selected coordinates must be distinct")

    cutoff_nm = _finite_real("cutoff_nm", cutoff_nm)
    gamma = _finite_real("gamma", gamma)
    if cutoff_nm < 0.4:
        raise ValueError("cutoff_nm must be at least 0.4")
    if gamma <= 0.0:
        raise ValueError("gamma must be positive")
    if not isinstance(n_modes, Integral) or isinstance(n_modes, (bool, np.bool_)):
        raise TypeError("n_modes must be an integer")
    n_modes = int(n_modes)
    if n_modes <= 0:
        raise ValueError("n_modes must be positive")

    hessian, graph = _network(coordinates, cutoff_nm, gamma)
    all_eigenvalues, all_modes = np.linalg.eigh(hessian)
    zero_count = int(np.sum(all_eigenvalues < _ZERO_THRESHOLD))
    positive = np.flatnonzero(all_eigenvalues >= _ZERO_THRESHOLD)
    if len(positive) == 0:
        raise ValueError("anisotropic network has no positive mode")
    chosen = positive[:n_modes]
    eigenvalues = all_eigenvalues[chosen]
    modes = all_modes[:, chosen]
    covariance = (modes * (1.0 / eigenvalues)[None, :]) @ modes.T
    msf, correlation = _statistics(covariance, len(indices))
    return {
        "node_indices": indices,
        "hessian": hessian,
        "zero_mode_count": zero_count,
        "component_count": _component_count(graph),
        "eigenvalues": eigenvalues,
        "modes": modes,
        "covariance": covariance,
        "msf": msf,
        "cross_correlation": correlation,
    }


__all__ = ["analyze_anm"]
