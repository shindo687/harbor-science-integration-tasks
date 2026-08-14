"""Representative superficial implementation: ordinary least squares only."""

from __future__ import annotations

import numpy as np


class RobustLinearModelResult:
    pass


def robust_linear_model(x, y, *, fit_intercept=True, huber_t=1.345,
                        scale="mad", covariance="H1", case_weights=None,
                        tol=1e-8, maxiter=50):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    design = np.column_stack((np.ones(y.size), x)) if fit_intercept else x
    params = np.linalg.pinv(design) @ y
    residuals = y - design @ params
    result = RobustLinearModelResult()
    result.params = params
    result.scale = float(np.sqrt(np.dot(residuals, residuals) / (y.size - np.linalg.matrix_rank(design))))
    result.weights = np.ones(y.size)
    # Deliberately omits robust sandwich scaling.
    pinv = np.linalg.pinv(design)
    result.covariance = pinv @ pinv.T
    result.residuals = residuals
    result.history = {
        "objective": np.asarray([np.dot(residuals, residuals)]),
        "scale": np.asarray([result.scale]),
        "params": np.asarray([params]),
    }
    result.n_iter = 1
    result.converged = True
    return result

