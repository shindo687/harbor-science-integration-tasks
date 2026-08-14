"""Huber robust linear regression for the bounded ALGOBRIDGE task.

This is a clean-room implementation from the mathematical task contract.
"""

from __future__ import annotations

import operator

import numpy as np
from scipy.special import ndtr


_NORMAL_75 = 0.6744897501960817


class RobustLinearModelResult:
    """Result returned by `robust_linear_model`."""

    __slots__ = (
        "params", "scale", "weights", "covariance", "residuals",
        "history", "n_iter", "converged",
    )

    def __init__(self, params, scale, weights, covariance, residuals,
                 history, n_iter, converged):
        self.params = params
        self.scale = scale
        self.weights = weights
        self.covariance = covariance
        self.residuals = residuals
        self.history = history
        self.n_iter = n_iter
        self.converged = converged


def _huber_rho(z, threshold):
    absolute = np.abs(z)
    return np.where(
        absolute <= threshold,
        0.5 * z**2,
        threshold * absolute - 0.5 * threshold**2,
    )


def _huber_psi(z, threshold):
    return np.where(np.abs(z) <= threshold, z, threshold * np.sign(z))


def _huber_weights(z, threshold):
    absolute = np.abs(z).copy()
    central = absolute <= threshold
    absolute[central] = 1.0
    return central + (~central) * threshold / absolute


def _mad_zero(residuals):
    return np.median(np.abs(residuals)) / _NORMAL_75


def _huber_scale(residuals, df_resid, *, threshold=2.5,
                 tolerance=1e-8, maxiter=30):
    nobs = residuals.size
    h = df_resid / nobs * (
        threshold**2
        + (1.0 - threshold**2) * ndtr(threshold)
        - 0.5
        - threshold / np.sqrt(2.0 * np.pi) * np.exp(-0.5 * threshold**2)
    )
    current = np.median(np.abs(residuals - np.median(residuals))) / _NORMAL_75
    previous = np.inf
    iteration = 1
    while abs(previous - current) > tolerance and iteration < maxiter:
        previous = current
        standardized = residuals / current
        chi = np.where(
            np.abs(standardized) < threshold,
            0.5 * standardized**2,
            0.5 * threshold**2,
        )
        current = np.sqrt(np.sum(chi) * previous**2 / (nobs * h))
        iteration += 1
    return current


def _estimate_scale(residuals, method, df_resid):
    if method == "mad":
        return _mad_zero(residuals)
    return _huber_scale(residuals, df_resid)


def _validate_inputs(x, y, fit_intercept, huber_t, scale, covariance,
                     case_weights, tol, maxiter):
    x = np.asarray(x, dtype=np.float64)
    y = np.asarray(y, dtype=np.float64)
    if x.ndim != 2:
        raise ValueError("x must be a two-dimensional array")
    if y.ndim != 1:
        raise ValueError("y must be a one-dimensional array")
    if x.shape[0] != y.size:
        raise ValueError("x and y must contain the same number of rows")
    if x.shape[0] == 0 or x.shape[1] == 0:
        raise ValueError("x must be non-empty")
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("x and y must contain only finite values")
    if not isinstance(fit_intercept, (bool, np.bool_)):
        raise TypeError("fit_intercept must be boolean")
    huber_t = float(huber_t)
    tol = float(tol)
    if not np.isfinite(huber_t) or huber_t <= 0:
        raise ValueError("huber_t must be finite and positive")
    if not np.isfinite(tol) or tol <= 0:
        raise ValueError("tol must be finite and positive")
    try:
        maxiter = operator.index(maxiter)
    except TypeError as exc:
        raise TypeError("maxiter must be an integer") from exc
    if maxiter <= 0:
        raise ValueError("maxiter must be positive")
    if not isinstance(scale, str) or scale.lower() not in {"mad", "huber"}:
        raise ValueError("scale must be 'mad' or 'huber'")
    if not isinstance(covariance, str) or covariance.upper() not in {"H1", "H2", "H3"}:
        raise ValueError("covariance must be 'H1', 'H2', or 'H3'")

    if case_weights is None:
        frequencies = np.ones(y.size, dtype=np.int64)
    else:
        raw = np.asarray(case_weights)
        if raw.ndim != 1 or raw.size != y.size:
            raise ValueError("case_weights must have one value per row")
        if not np.issubdtype(raw.dtype, np.number):
            raise TypeError("case_weights must be numeric")
        numeric = np.asarray(raw, dtype=np.float64)
        if (not np.all(np.isfinite(numeric)) or np.any(numeric < 1)
                or np.any(numeric != np.floor(numeric))):
            raise ValueError("case_weights must be positive integers")
        frequencies = numeric.astype(np.int64)

    design = np.column_stack((np.ones(y.size), x)) if fit_intercept else x
    expanded_design = np.repeat(design, frequencies, axis=0)
    expanded_y = np.repeat(y, frequencies)
    rank = np.linalg.matrix_rank(expanded_design)
    if expanded_design.shape[0] <= rank:
        raise ValueError("effective observations must exceed the design rank")
    first = np.cumsum(np.r_[0, frequencies[:-1]])
    return (
        x, y, design, expanded_design, expanded_y, first, huber_t,
        scale.lower(), covariance.upper(), tol, maxiter,
    )


def robust_linear_model(x, y, *, fit_intercept=True, huber_t=1.345,
                        scale="mad", covariance="H1", case_weights=None,
                        tol=1e-8, maxiter=50):
    """Fit a linear model with Huber's T norm using IRLS.

    `case_weights` are positive integer frequency weights. See the task
    contract for the intentionally bounded API.
    """
    (
        x, y, original_design, design, response, first, threshold,
        scale_method, cov_kind, tolerance, max_iterations,
    ) = _validate_inputs(
        x, y, fit_intercept, huber_t, scale, covariance,
        case_weights, tol, maxiter,
    )

    nobs, nparams = design.shape
    rank = np.linalg.matrix_rank(design)
    df_resid = float(nobs - rank)
    df_model = float(rank - 1)
    pinv_design = np.linalg.pinv(design)
    normalized_covariance = pinv_design @ pinv_design.T

    params = pinv_design @ response
    residuals = response - design @ params
    robust_scale = _estimate_scale(residuals, scale_method, df_resid)

    initial_variance = np.dot(residuals, residuals) / df_resid
    objective_history = [float(np.sum(_huber_rho(
        residuals / initial_variance, threshold,
    )))]
    scale_history = [float(robust_scale)]
    params_history = [params.copy()]
    iteration = 1
    final_weights = None

    while True:
        if robust_scale == 0.0:
            break
        final_weights = _huber_weights(residuals / robust_scale, threshold)
        square_root_weights = np.sqrt(final_weights)
        weighted_design = square_root_weights[:, None] * design
        weighted_response = square_root_weights * response
        params = np.linalg.pinv(weighted_design) @ weighted_response
        residuals = response - design @ params
        weighted_residuals = square_root_weights * residuals
        weighted_variance = (
            np.dot(weighted_residuals, weighted_residuals) / (nobs - nparams)
        )
        robust_scale = _estimate_scale(residuals, scale_method, df_resid)
        params_history.append(params.copy())
        scale_history.append(float(robust_scale))
        objective_history.append(float(np.sum(_huber_rho(
            residuals / weighted_variance, threshold,
        ))))
        iteration += 1
        difference = abs(objective_history[-1] - objective_history[-2])
        if difference <= tolerance or iteration >= max_iterations:
            break

    if final_weights is None:
        final_weights = np.ones(nobs, dtype=np.float64)

    standardized = residuals / robust_scale if robust_scale != 0 else np.zeros_like(residuals)
    psi = _huber_psi(standardized, threshold)
    psi_derivative = (np.abs(standardized) <= threshold).astype(np.float64)
    mean_derivative = np.mean(psi_derivative)
    derivative_variance = np.var(psi_derivative)
    correction = (
        1.0
        + (df_model + 1.0) / nobs
        * derivative_variance / mean_derivative**2
    )

    if cov_kind == "H1":
        covariance_matrix = (
            correction**2
            * (np.sum(psi**2) * robust_scale**2 / df_resid)
            / (np.sum(psi_derivative) / nobs) ** 2
            * normalized_covariance
        )
    else:
        sensitivity = (psi_derivative * design.T) @ design
        sensitivity_inverse = np.linalg.inv(sensitivity)
        if cov_kind == "H2":
            covariance_matrix = (
                correction
                * np.sum(psi**2) * robust_scale**2 / df_resid
                / (np.sum(psi_derivative) / nobs)
                * sensitivity_inverse
            )
        else:
            covariance_matrix = (
                np.sum(psi**2) * robust_scale**2
                / (correction * df_resid)
                * sensitivity_inverse @ (design.T @ design) @ sensitivity_inverse
            )

    finite_convergence = (
        len(objective_history) > 1
        and abs(objective_history[-1] - objective_history[-2]) <= tolerance
    )
    original_residuals = y - original_design @ params
    history = {
        "objective": np.asarray(objective_history),
        "scale": np.asarray(scale_history),
        "params": np.asarray(params_history),
    }
    return RobustLinearModelResult(
        params=np.asarray(params),
        scale=float(robust_scale),
        weights=np.asarray(final_weights[first]),
        covariance=np.asarray(covariance_matrix),
        residuals=np.asarray(original_residuals),
        history=history,
        n_iter=iteration,
        converged=bool(finite_convergence),
    )


__all__ = ["RobustLinearModelResult", "robust_linear_model"]

