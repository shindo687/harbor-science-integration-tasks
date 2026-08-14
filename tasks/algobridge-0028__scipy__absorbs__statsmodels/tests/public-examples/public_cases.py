"""Five deterministic public examples."""

from __future__ import annotations

import numpy as np


def _linear(seed, n, p, noise=0.15, intercept=1.25):
    rng = np.random.default_rng(seed)
    x = rng.normal(size=(n, p))
    beta = np.linspace(0.9, -0.7, p)
    y = intercept + x @ beta + rng.normal(scale=noise, size=n)
    return x, y


def _case(name, x, y, **options):
    return {
        "name": name,
        "x": np.asarray(x, dtype=float).tolist(),
        "y": np.asarray(y, dtype=float).tolist(),
        "options": options,
    }


def public_cases():
    cases = []
    x, y = _linear(8201, 20, 2)
    cases.append(_case("public_clean_h1", x, y))

    x, y = _linear(8202, 24, 3)
    y[6] += 10.0
    cases.append(_case("public_outlier_h2", x, y, covariance="H2", huber_t=1.1))

    x, y = _linear(8203, 26, 2, intercept=0.0)
    y[17] -= 6.0
    cases.append(_case(
        "public_no_intercept_h3", x, y,
        fit_intercept=False, covariance="H3",
    ))

    x, y = _linear(8204, 16, 2)
    frequencies = [1, 2, 1, 3, 1, 1, 2, 1, 4, 1, 2, 1, 1, 3, 1, 2]
    cases.append(_case(
        "public_frequency_weights", x, y,
        case_weights=frequencies, covariance="H2",
    ))

    x, y = _linear(8205, 30, 3, noise=0.25)
    y[[3, 22]] += [8.0, -7.0]
    cases.append(_case(
        "public_huber_scale", x, y,
        scale="huber", covariance="H1",
    ))
    return cases

