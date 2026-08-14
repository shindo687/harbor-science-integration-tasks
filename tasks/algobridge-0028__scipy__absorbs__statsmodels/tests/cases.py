"""Deterministic hidden fixtures for ALGOBRIDGE-0028."""

from __future__ import annotations

import numpy as np


def _linear(seed, n=24, p=3, noise=0.18, *, intercept=1.7):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, p))
    beta = np.linspace(0.8, -1.2, p)
    y = intercept + x @ beta + rng.normal(scale=noise, size=n)
    return x, y


def _case(name, x, y, **options):
    return {
        "name": name,
        "x": np.asarray(x, dtype=np.float64).tolist(),
        "y": np.asarray(y, dtype=np.float64).tolist(),
        "options": options,
    }


def hidden_cases():
    cases = []

    x, y = _linear(2801, n=28, p=3, noise=0.12)
    cases.append(_case("clean_intercept_mad_h1", x, y))

    x, y = _linear(2802, n=25, p=2, noise=0.2, intercept=0.0)
    cases.append(_case(
        "clean_no_intercept_mad_h1", x, y,
        fit_intercept=False, huber_t=1.5,
    ))

    x, y = _linear(2803, n=30, p=3)
    y[4] += 18.0
    cases.append(_case("positive_outlier_mad_h1", x, y, huber_t=1.2))

    x, y = _linear(2804, n=26, p=2)
    y[[2, 19]] -= [13.0, 8.0]
    cases.append(_case("negative_outliers_mad_h2", x, y, covariance="H2"))

    x, y = _linear(2805, n=32, p=3)
    x[7] = [12.0, -9.0, 7.0]
    y[7] += 15.0
    cases.append(_case("high_leverage_mad_h3", x, y, covariance="H3"))

    x, y = _linear(2806, n=18, p=2)
    y[5] += 9.0
    frequencies = np.array([1, 2, 1, 3, 1, 1, 4, 1, 2, 1, 1, 3, 1, 2, 1, 1, 2, 1])
    cases.append(_case(
        "frequency_weights_intercept", x, y,
        covariance="H2", case_weights=frequencies.tolist(),
    ))

    x, y = _linear(2807, n=20, p=3, intercept=0.0)
    y[12] -= 7.5
    frequencies = np.array([1, 1, 2, 1, 3, 1, 1, 2, 1, 1, 1, 4, 1, 2, 1, 1, 3, 1, 2, 1])
    cases.append(_case(
        "frequency_weights_no_intercept", x, y,
        fit_intercept=False, covariance="H3",
        case_weights=frequencies.tolist(), huber_t=1.1,
    ))

    rng = np.random.default_rng(2808)
    base = rng.normal(size=(27, 2))
    x = np.column_stack((base, base[:, 0] - 2.0 * base[:, 1]))
    y = 0.4 + 1.1 * base[:, 0] - 0.6 * base[:, 1] + rng.normal(scale=0.16, size=27)
    y[9] += 6.0
    cases.append(_case("rank_deficient_mad_h1", x, y))

    x, y = _linear(2809, n=22, p=2, noise=2e-7)
    y[3] += 1.4e-6
    cases.append(_case(
        "near_zero_scale", x, y, huber_t=0.9, tol=1e-10,
    ))

    x, y = _linear(2810, n=34, p=4, noise=0.3)
    y[[1, 11, 29]] += [10.0, -7.0, 13.0]
    cases.append(_case("huber_scale_h1", x, y, scale="huber"))

    x, y = _linear(2811, n=38, p=3, noise=0.24)
    y[[8, 31]] -= [11.0, 9.0]
    cases.append(_case(
        "huber_scale_h2_alternate_t", x, y,
        scale="huber", covariance="H2", huber_t=0.85,
    ))

    x, y = _linear(2812, n=29, p=3, noise=0.25)
    y[[0, 6, 24]] += [12.0, -8.0, 9.0]
    cases.append(_case(
        "bounded_iterations_h3", x, y,
        covariance="H3", huber_t=1.05, maxiter=7, tol=1e-14,
    ))

    return cases


POINT_NAMES = [
    "clean_intercept_mad_h1",
    "clean_no_intercept_mad_h1",
    "positive_outlier_mad_h1",
    "negative_outliers_mad_h2",
    "high_leverage_mad_h3",
    "frequency_weights_intercept",
    "frequency_weights_no_intercept",
    "rank_deficient_mad_h1",
    "near_zero_scale",
    "huber_scale_h1",
    "huber_scale_h2_alternate_t",
    "bounded_iterations_h3",
    "huber_estimating_equation",
    "unit_equivariance_and_clean_ols",
    "api_isolation_and_host_regression",
]

