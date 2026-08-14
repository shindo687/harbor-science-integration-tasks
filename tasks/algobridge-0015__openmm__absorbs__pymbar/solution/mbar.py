"""Clean-room bounded MBAR estimator for OpenMM's application layer."""

from __future__ import annotations

import numpy as np


def _logsumexp(values, axis=None):
    values = np.asarray(values, dtype=np.float64)
    maximum = np.max(values, axis=axis, keepdims=True)
    shifted = np.exp(values - maximum)
    result = maximum + np.log(np.sum(shifted, axis=axis, keepdims=True))
    if axis is None:
        return float(result.reshape(-1)[0])
    return np.squeeze(result, axis=axis)


def _validate(u_kn, N_k, initial_f_k, relative_tolerance, maximum_iterations):
    u = np.asarray(u_kn, dtype=np.float64)
    if u.ndim != 2 or u.shape[0] < 2 or u.shape[1] < 2:
        raise ValueError("u_kn must be a finite K by N matrix with K,N >= 2")
    if not np.all(np.isfinite(u)):
        raise ValueError("u_kn must contain only finite values")
    # A configuration-dependent offset shared by every state cancels from the
    # MBAR equations. Remove it up front to retain precision for large values.
    u = u - np.min(u, axis=0, keepdims=True)
    raw_counts = np.asarray(N_k)
    if raw_counts.ndim != 1 or raw_counts.shape[0] != u.shape[0]:
        raise ValueError("N_k must contain one count per state")
    if not np.all(np.isfinite(raw_counts.astype(np.float64))):
        raise ValueError("N_k must be finite")
    counts = raw_counts.astype(np.int64)
    if not np.array_equal(raw_counts, counts) or np.any(counts < 0):
        raise ValueError("N_k must contain nonnegative integers")
    if int(np.sum(counts)) != u.shape[1] or not np.any(counts > 0):
        raise ValueError("sum(N_k) must equal the number of samples")
    tolerance = float(relative_tolerance)
    if not np.isfinite(tolerance) or tolerance <= 0:
        raise ValueError("relative_tolerance must be finite and positive")
    limit = int(maximum_iterations)
    if limit != maximum_iterations or limit <= 0:
        raise ValueError("maximum_iterations must be a positive integer")
    if initial_f_k is None:
        free = np.zeros(u.shape[0], dtype=np.float64)
    else:
        free = np.asarray(initial_f_k, dtype=np.float64)
        if free.shape != (u.shape[0],) or not np.all(np.isfinite(free)):
            raise ValueError("initial_f_k must be a finite length-K vector")
        free = free.copy()
    free -= free[0]
    return u, counts, free, tolerance, limit


def _denominator(u, counts, free):
    sampled = counts > 0
    terms = (np.log(counts[sampled]) + free[sampled])[:, None] - u[sampled]
    return _logsumexp(terms, axis=0)


def _self_consistent(u, counts, free, tolerance, budget):
    sampled = np.flatnonzero(counts > 0)
    iterations = 0
    # Stable fixed-point sweeps quickly absorb large additive state offsets and
    # give Newton a well-scaled starting point.
    for _ in range(min(80, budget)):
        denominator = _denominator(u, counts, free)
        updated = -_logsumexp(-u - denominator[None, :], axis=1)
        updated -= updated[0]
        change = float(np.max(np.abs(updated[sampled] - free[sampled])))
        free = updated
        iterations += 1
        if change <= max(1e-5, np.sqrt(tolerance)):
            break

    anchor = int(sampled[0])
    active = sampled[sampled != anchor]
    while iterations < budget and active.size:
        denominator = _denominator(u, counts, free)
        probabilities = np.exp(
            (np.log(counts[sampled]) + free[sampled])[:, None]
            - u[sampled] - denominator[None, :]
        )
        gradient = probabilities.sum(axis=1) - counts[sampled]
        active_mask = sampled != anchor
        reduced_gradient = gradient[active_mask]
        residual = float(np.max(np.abs(reduced_gradient)))
        # Below roughly 1e-10 the gradient is dominated by cancellation in
        # large free-energy gauges; extra Newton steps can make the estimate
        # worse rather than more accurate in float64.
        if residual <= max(tolerance, 1e-10):
            break
        hessian = np.diag(probabilities.sum(axis=1)) - probabilities @ probabilities.T
        reduced_hessian = hessian[np.ix_(active_mask, active_mask)]
        try:
            step = np.linalg.solve(reduced_hessian, -reduced_gradient)
        except np.linalg.LinAlgError:
            step = -np.linalg.pinv(reduced_hessian, rcond=1e-13) @ reduced_gradient

        old_objective = float(np.sum(denominator) - np.dot(counts[sampled], free[sampled]))
        accepted = False
        factor = 1.0
        for _ in range(40):
            trial = free.copy()
            trial[active] += factor * step
            trial -= trial[anchor]
            trial_denominator = _denominator(u, counts, trial)
            objective = float(
                np.sum(trial_denominator) - np.dot(counts[sampled], trial[sampled])
            )
            if np.isfinite(objective) and objective <= old_objective + 1e-13:
                free = trial
                accepted = True
                break
            factor *= 0.5
        if not accepted:
            # A fixed-point step is a safe fallback for singular/low-overlap cases.
            updated = -_logsumexp(-u - denominator[None, :], axis=1)
            updated -= updated[anchor]
            free[sampled] = updated[sampled]
        iterations += 1

    denominator = _denominator(u, counts, free)
    free = -_logsumexp(-u - denominator[None, :], axis=1)
    free -= free[0]
    denominator = _denominator(u, counts, free)
    weights = np.exp(free[None, :] - u.T - denominator[:, None])
    residual = float(np.max(np.abs(weights.sum(axis=0) - 1.0)))
    return free, weights, iterations, residual


def _covariance(weights, counts):
    gram = weights.T @ weights
    eigenvalues, vectors = np.linalg.eigh(gram)
    eigenvalues = np.maximum(eigenvalues, 0.0)
    sigma = np.diag(np.sqrt(eigenvalues))
    middle = np.eye(len(counts)) - sigma @ vectors.T @ np.diag(counts) @ vectors @ sigma
    theta = vectors @ sigma @ np.linalg.pinv(middle, rcond=1e-10) @ sigma @ vectors.T
    return 0.5 * (theta + theta.T)


def estimate_mbar(u_kn, N_k, *, initial_f_k=None, relative_tolerance=1e-10,
                  maximum_iterations=10000):
    """Estimate bounded multistate free energies from reduced potentials."""
    u, counts, free, tolerance, limit = _validate(
        u_kn, N_k, initial_f_k, relative_tolerance, maximum_iterations
    )
    free, weights, iterations, residual = _self_consistent(
        u, counts, free, tolerance, limit
    )
    if residual > max(5e-8, 100*tolerance):
        raise RuntimeError("MBAR equations did not converge")
    covariance = _covariance(weights, counts)
    diagonal = np.diag(covariance)
    variance = diagonal[:, None] + diagonal[None, :] - 2.0*covariance
    uncertainty = np.sqrt(np.maximum(variance, 0.0))
    delta = free[None, :] - free[:, None]
    gram = weights.T @ weights
    overlap = gram * counts[None, :]
    effective = 1.0 / np.sum(weights*weights, axis=0)
    return {
        "f_k": free,
        "Delta_f": delta,
        "dDelta_f": uncertainty,
        "covariance": covariance,
        "weights": weights,
        "overlap": overlap,
        "effective_sample_number": effective,
        "iterations": iterations,
        "residual": residual,
        "converged": True,
    }
