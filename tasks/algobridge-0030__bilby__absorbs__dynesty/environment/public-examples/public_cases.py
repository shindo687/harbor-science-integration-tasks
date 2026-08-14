"""Five lightweight public problems for ALGOBRIDGE-0030."""

from __future__ import annotations

import math

import numpy as np


def _normal_1d():
    def transform(u):
        return np.asarray([-6.0 + 12.0 * u[0]])

    def loglike(x):
        return -0.5 * (x[0] / 0.75) ** 2

    return transform, loglike, 1, {"mean": [0.0], "logz": math.log(0.75 * math.sqrt(2 * math.pi) / 12.0)}


def _shifted_1d():
    def transform(u):
        return np.asarray([-4.0 + 10.0 * u[0]])

    def loglike(x):
        return -0.5 * ((x[0] - 1.25) / 0.6) ** 2

    return transform, loglike, 1, {"mean": [1.25], "logz": math.log(0.6 * math.sqrt(2 * math.pi) / 10.0)}


def _correlated_2d():
    covariance = np.asarray([[0.7, 0.32], [0.32, 0.5]])
    precision = np.linalg.inv(covariance)

    def transform(u):
        return -5.0 + 10.0 * np.asarray(u)

    def loglike(x):
        delta = np.asarray(x) - np.asarray([0.4, -0.7])
        return -0.5 * float(delta @ precision @ delta)

    logz = math.log(2 * math.pi * math.sqrt(np.linalg.det(covariance)) / 100.0)
    return transform, loglike, 2, {"mean": [0.4, -0.7], "logz": logz}


def _flat_1d():
    def transform(u):
        return np.asarray([-2.0 + 4.0 * u[0]])

    def loglike(x):
        return -0.75

    return transform, loglike, 1, {"mean": [0.0], "logz": -0.75}


def _hard_boundary():
    def transform(u):
        return np.asarray([-3.0 + 6.0 * u[0]])

    def loglike(x):
        return 0.0 if -0.5 <= x[0] <= 1.0 else -35.0

    return transform, loglike, 1, {"mean": [0.25], "logz": math.log(1.5 / 6.0)}


CASES = {
    "normal_1d": _normal_1d,
    "shifted_1d": _shifted_1d,
    "correlated_2d": _correlated_2d,
    "flat_1d": _flat_1d,
    "hard_boundary": _hard_boundary,
}


def load_case(name):
    return CASES[name]()

