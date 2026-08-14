"""Discrete Markov-state-model estimation for :mod:`openmm.app`.

This bounded implementation depends only on NumPy.  It implements transition
counting, largest-component selection, reversible maximum-likelihood
estimation, and basic spectral kinetics for discrete state trajectories.
"""

from __future__ import annotations

import math

import numpy as np


def _as_trajectories(trajectories):
    if isinstance(trajectories, (str, bytes)):
        raise TypeError("trajectories must contain integer state labels")
    try:
        outer = list(trajectories)
    except TypeError as exc:
        raise TypeError("trajectories must be an iterable") from exc
    if not outer:
        raise ValueError("at least one trajectory is required")

    if all(isinstance(value, (int, np.integer)) and not isinstance(value, bool)
           for value in outer):
        outer = [outer]

    result = []
    for trajectory in outer:
        if isinstance(trajectory, (str, bytes)):
            raise TypeError("each trajectory must be an integer sequence")
        try:
            values = list(trajectory)
        except TypeError as exc:
            raise TypeError("each trajectory must be an iterable") from exc
        if not values:
            raise ValueError("trajectories must not be empty")
        normalized = []
        for value in values:
            if not isinstance(value, (int, np.integer)) or isinstance(value, bool):
                raise TypeError("state labels must be integers")
            value = int(value)
            if value < 0:
                raise ValueError("state labels must be non-negative")
            normalized.append(value)
        result.append(normalized)
    return result


def _count_transitions(trajectories, lag, count_mode):
    nstates = 1 + max(max(trajectory) for trajectory in trajectories)
    counts = np.zeros((nstates, nstates), dtype=np.int64)
    total = 0
    for trajectory in trajectories:
        stop = len(trajectory) - lag
        starts = range(0, max(0, stop), 1 if count_mode == "sliding" else lag)
        for start in starts:
            counts[trajectory[start], trajectory[start + lag]] += 1
            total += 1
    if total == 0:
        raise ValueError("no lagged transition can be counted")
    return counts


def _largest_component(counts):
    adjacency = (counts + counts.T) > 0
    eligible = np.flatnonzero(np.any(adjacency, axis=1))
    components = []
    unseen = set(int(value) for value in eligible)
    while unseen:
        seed = min(unseen)
        unseen.remove(seed)
        component = []
        stack = [seed]
        while stack:
            state = stack.pop()
            component.append(state)
            neighbors = set(int(value) for value in np.flatnonzero(adjacency[state]))
            pending = neighbors & unseen
            unseen.difference_update(pending)
            stack.extend(sorted(pending, reverse=True))
        components.append(sorted(component))
    if not components:
        raise ValueError("the transition graph is empty")
    return np.asarray(min(components, key=lambda values: (-len(values), values[0])),
                      dtype=int)


def _reversible_transition_matrix(counts, tolerance=1e-13, maximum_iterations=1000000):
    counts = np.asarray(counts, dtype=float)
    row_counts = counts.sum(axis=1)
    support = row_counts + counts.sum(axis=0)
    stationary = support / support.sum()
    symmetric_counts = counts + counts.T

    for _ in range(maximum_iterations):
        denominators = (
            row_counts[:, None] / stationary[:, None]
            + row_counts[None, :] / stationary[None, :]
        )
        flux = np.divide(
            symmetric_counts, denominators,
            out=np.zeros_like(symmetric_counts), where=denominators > 0,
        )
        updated = flux.sum(axis=1)
        updated /= updated.sum()
        error = np.linalg.norm((updated - stationary) / (updated + stationary))
        stationary = updated
        if error < tolerance:
            break
    else:
        raise RuntimeError("reversible maximum-likelihood iteration did not converge")

    denominators = (
        row_counts[:, None] / stationary[:, None]
        + row_counts[None, :] / stationary[None, :]
    )
    flux = np.divide(
        symmetric_counts, denominators,
        out=np.zeros_like(symmetric_counts), where=denominators > 0,
    )
    transition = flux / stationary[:, None]
    transition /= transition.sum(axis=1)[:, None]
    stationary /= stationary.sum()
    return transition, stationary


def _stationary_distribution(transition):
    nstates = transition.shape[0]
    system = np.vstack((transition.T - np.eye(nstates), np.ones(nstates)))
    target = np.concatenate((np.zeros(nstates), [1.0]))
    stationary, _, _, _ = np.linalg.lstsq(system, target, rcond=None)
    stationary[np.abs(stationary) < 1e-15] = 0.0
    if np.min(stationary) < -1e-10:
        raise RuntimeError("could not determine a non-negative stationary distribution")
    stationary = np.maximum(stationary, 0.0)
    stationary /= stationary.sum()
    return stationary


def _nonreversible_transition_matrix(counts):
    counts = np.asarray(counts, dtype=float)
    totals = counts.sum(axis=1)
    transition = np.zeros_like(counts)
    nonempty = totals > 0
    transition[nonempty] = counts[nonempty] / totals[nonempty, None]
    for state in np.flatnonzero(~nonempty):
        transition[state, state] = 1.0
    return transition, _stationary_distribution(transition)


def _spectrum(transition, lag):
    values = [complex(value) for value in np.linalg.eigvals(transition)]
    stationary_index = min(range(len(values)), key=lambda i: abs(values[i] - 1.0))
    stationary_value = values.pop(stationary_index)
    values.sort(key=lambda value: (-abs(value), -value.real, -value.imag))
    ordered = [stationary_value, *values]
    timescales = []
    for value in ordered[1:]:
        magnitude = abs(value)
        if magnitude <= 1e-14:
            timescales.append(0.0)
        elif abs(magnitude - 1.0) <= 1e-14:
            timescales.append(None)
        else:
            timescales.append(-float(lag) / math.log(magnitude))
    return np.asarray(ordered, dtype=complex), timescales


def estimate_markov_model(trajectories, lag=1, count_mode="sliding",
                          reversible=True, connectivity="largest"):
    """Estimate a bounded discrete Markov-state model.

    Parameters and return values follow the task contract documented in
    ``instruction.md``.  State labels in ``active_set`` retain their original
    values even when labels are non-contiguous.
    """
    if not isinstance(lag, (int, np.integer)) or isinstance(lag, bool):
        raise TypeError("lag must be an integer")
    lag = int(lag)
    if lag <= 0:
        raise ValueError("lag must be positive")
    if count_mode not in ("sliding", "sample"):
        raise ValueError("count_mode must be 'sliding' or 'sample'")
    if not isinstance(reversible, (bool, np.bool_)):
        raise TypeError("reversible must be a boolean")
    if connectivity != "largest":
        raise ValueError("only connectivity='largest' is supported")

    normalized = _as_trajectories(trajectories)
    full_counts = _count_transitions(normalized, lag, count_mode)
    active_set = _largest_component(full_counts)
    counts = full_counts[np.ix_(active_set, active_set)]
    if reversible:
        transition, stationary = _reversible_transition_matrix(counts)
    else:
        transition, stationary = _nonreversible_transition_matrix(counts)
    eigenvalues, timescales = _spectrum(transition, lag)
    return {
        "active_set": active_set,
        "count_matrix": counts,
        "transition_matrix": transition,
        "stationary_distribution": stationary,
        "eigenvalues": eigenvalues,
        "timescales": timescales,
    }


__all__ = ["estimate_markov_model"]
