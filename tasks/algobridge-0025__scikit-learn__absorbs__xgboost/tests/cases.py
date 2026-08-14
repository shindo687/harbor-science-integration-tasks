"""Deterministic hidden exact-boosting cases."""

from __future__ import annotations

import copy
import numpy as np


def _params(objective="squared_error", **overrides):
    values = {
        "objective": objective,
        "n_estimators": 4,
        "max_depth": 2,
        "learning_rate": 0.3,
        "reg_lambda": 1.0,
        "reg_alpha": 0.0,
        "min_split_loss": 0.0,
    }
    values.update(overrides)
    return values


def _item(name, X, y, *, params=None, sample_weight=None, test_X=None):
    result = {
        "name": name,
        "X": np.asarray(X, dtype=float).tolist(),
        "y": np.asarray(y, dtype=float).tolist(),
        "params": params or _params(),
    }
    if sample_weight is not None:
        result["sample_weight"] = np.asarray(sample_weight, dtype=float).tolist()
    if test_X is not None:
        result["test_X"] = np.asarray(test_X, dtype=float).tolist()
    return result


def hidden_cases():
    rng = np.random.default_rng(2501)
    x1 = np.linspace(-2.0, 2.0, 12)
    basic_X = np.column_stack([x1, np.sin(1.7 * x1)])
    basic_y = np.where(x1 < -0.5, -1.2, np.where(x1 < 0.9, 0.4, 2.1))

    depth_X = rng.normal(size=(28, 4))
    depth_y = (
        1.3 * (depth_X[:, 0] > -0.2)
        - 0.9 * (depth_X[:, 1] > 0.5)
        + 0.7 * (depth_X[:, 2] < -0.4)
        + 0.15 * depth_X[:, 3]
    )

    weighted_X = np.column_stack([
        np.linspace(-1.5, 1.5, 15),
        np.cos(np.linspace(-1.5, 1.5, 15) * 2.1),
    ])
    weighted_y = np.array([-2, -2, -1, -1, -1, 0, 0, 0, 1, 1, 1, 3, 3, 4, 4], float)
    weighted_w = np.array([1, 2, 1, 3, 1, 1, 2, 4, 1, 2, 1, 1, 3, 1, 2], float)

    missing_right_X = np.array([
        [-2.0, 0.0], [-1.0, 0.2], [0.0, 0.4], [1.0, 0.6],
        [2.0, 0.8], [3.0, 1.0], [np.nan, 0.1], [np.nan, 0.9],
    ])
    missing_right_y = np.array([-2, -2, 0, 0, 2, 2, 2, 2], float)
    missing_left_y = np.array([-2, -2, 0, 0, 2, 2, -2, -2], float)

    constant_X = np.array([
        [1.0, -2.0], [1.0, -1.0], [1.0, 0.0], [1.0, 1.0],
        [np.nan, 2.0], [np.nan, 3.0], [1.0, 4.0], [1.0, 5.0],
    ])
    constant_y = np.array([0, 0, 0, 1, 3, 3, 1, 1], float)

    l1_X = np.arange(12, dtype=float).reshape(-1, 1)
    l1_y = np.array([-4, -4, -4, -4, -0.05, 0.05, -0.05, 0.05, 3, 3, 3, 3], float)

    logistic_X = rng.normal(size=(24, 3))
    logistic_signal = 1.4 * logistic_X[:, 0] - 0.8 * logistic_X[:, 1] + 0.3 * logistic_X[:, 2]
    logistic_y = (logistic_signal > 0.1).astype(float)

    logistic_depth_X = rng.normal(size=(36, 5))
    logistic_depth_y = (
        (logistic_depth_X[:, 0] > 0.2)
        ^ (logistic_depth_X[:, 1] < -0.4)
        ^ (logistic_depth_X[:, 2] > 0.8)
    ).astype(float)

    logistic_missing_X = rng.normal(size=(26, 3))
    logistic_missing_X[[1, 5, 9, 18], 0] = np.nan
    logistic_missing_X[[2, 7, 20], 2] = np.nan
    logistic_missing_y = (
        np.nan_to_num(logistic_missing_X[:, 0], nan=1.5)
        + 0.6 * np.nan_to_num(logistic_missing_X[:, 2], nan=-1.0)
        > 0.2
    ).astype(float)
    logistic_weight = np.linspace(0.7, 2.2, 26)

    tie_axis = np.array([-2, -2, -1, -1, 1, 1, 2, 2], float)
    tie_X = np.column_stack([tie_axis, tie_axis, np.ones_like(tie_axis)])
    tie_y = np.array([-1, -1, -1, -1, 2, 2, 2, 2], float)

    permutation_X = rng.normal(size=(20, 4))
    permutation_X[[3, 11], 1] = np.nan
    permutation_y = (
        1.2 * np.nan_to_num(permutation_X[:, 1], nan=-0.8)
        - 0.7 * permutation_X[:, 2]
        + (permutation_X[:, 0] > 0.0)
    )
    permutation_w = np.linspace(0.5, 2.0, 20)
    order = np.array([7, 1, 18, 4, 12, 0, 16, 9, 2, 15, 5, 19, 8, 3, 14, 6, 11, 17, 10, 13])
    permutation_test = np.array([
        [-1.0, -0.8, 0.2, 0.0], [0.5, np.nan, -0.4, 1.0],
        [1.2, 0.7, 0.8, -0.3], [0.0, -0.2, -1.1, 0.4],
    ])

    return [
        _item("regression_stump", basic_X, basic_y,
              params=_params(n_estimators=3, max_depth=1),
              test_X=[[-2.3, 0.1], [-0.2, -0.3], [1.7, 0.2]]),
        _item("regression_depth_three", depth_X, depth_y,
              params=_params(n_estimators=5, max_depth=3, learning_rate=0.2,
                             reg_lambda=0.7)),
        _item("weighted_regression", weighted_X, weighted_y,
              params=_params(n_estimators=5, reg_lambda=1.4),
              sample_weight=weighted_w),
        _item("missing_default_right", missing_right_X, missing_right_y,
              params=_params(n_estimators=3, max_depth=2),
              test_X=[[np.nan, 0.5], [-1.5, 0.5], [2.5, 0.5]]),
        _item("missing_default_left", missing_right_X, missing_left_y,
              params=_params(n_estimators=3, max_depth=2),
              test_X=[[np.nan, 0.5], [-1.5, 0.5], [2.5, 0.5]]),
        _item("constant_with_missing", constant_X, constant_y,
              params=_params(n_estimators=3, max_depth=2, reg_lambda=0.5)),
        _item("l1_zero_leaf", l1_X, l1_y,
              params=_params(n_estimators=2, max_depth=2, reg_lambda=0.5,
                             reg_alpha=0.4)),
        _item("gamma_pruning", depth_X[:18], depth_y[:18],
              params=_params(n_estimators=3, max_depth=3,
                             min_split_loss=4.0)),
        _item("logistic_stump", logistic_X, logistic_y,
              params=_params("logistic", n_estimators=5, max_depth=1,
                             learning_rate=0.25)),
        _item("logistic_depth_three", logistic_depth_X, logistic_depth_y,
              params=_params("logistic", n_estimators=6, max_depth=3,
                             learning_rate=0.2, reg_lambda=0.8)),
        _item("logistic_weighted_missing", logistic_missing_X,
              logistic_missing_y,
              params=_params("logistic", n_estimators=5, max_depth=2,
                             reg_alpha=0.15), sample_weight=logistic_weight),
        _item("learning_rate_zero", basic_X, basic_y,
              params=_params(n_estimators=4, max_depth=2,
                             learning_rate=0.0)),
        _item("feature_split_tie", tie_X, tie_y,
              params=_params(n_estimators=2, max_depth=2,
                             learning_rate=0.4, reg_lambda=0.3)),
        _item("row_permutation_base", permutation_X, permutation_y,
              params=_params(n_estimators=4, max_depth=3,
                             learning_rate=0.2, reg_lambda=0.9,
                             reg_alpha=0.1), sample_weight=permutation_w,
              test_X=permutation_test),
        _item("row_permutation_shuffled", permutation_X[order],
              permutation_y[order],
              params=_params(n_estimators=4, max_depth=3,
                             learning_rate=0.2, reg_lambda=0.9,
                             reg_alpha=0.1), sample_weight=permutation_w[order],
              test_X=permutation_test),
    ]


def invalid_cases():
    base = hidden_cases()[0]
    result = []

    too_few = copy.deepcopy(base)
    too_few["name"] = "invalid_too_few_rows"
    too_few["X"] = too_few["X"][:3]
    too_few["y"] = too_few["y"][:3]
    result.append(too_few)

    infinity = copy.deepcopy(base)
    infinity["name"] = "invalid_infinite_feature"
    infinity["X"][0][0] = float("inf")
    result.append(infinity)

    all_missing = copy.deepcopy(base)
    all_missing["name"] = "invalid_all_missing_feature"
    for row in all_missing["X"]:
        row[0] = float("nan")
    result.append(all_missing)

    bad_target = copy.deepcopy(base)
    bad_target["name"] = "invalid_logistic_target"
    bad_target["params"]["objective"] = "logistic"
    bad_target["y"][0] = 0.25
    result.append(bad_target)

    zero_weight = copy.deepcopy(base)
    zero_weight["name"] = "invalid_zero_weight"
    zero_weight["sample_weight"] = [1.0] * len(zero_weight["y"])
    zero_weight["sample_weight"][1] = 0.0
    result.append(zero_weight)

    bad_estimators = copy.deepcopy(base)
    bad_estimators["name"] = "invalid_n_estimators"
    bad_estimators["params"]["n_estimators"] = 0
    result.append(bad_estimators)

    bad_depth = copy.deepcopy(base)
    bad_depth["name"] = "invalid_max_depth"
    bad_depth["params"]["max_depth"] = 4
    result.append(bad_depth)

    bad_rate = copy.deepcopy(base)
    bad_rate["name"] = "invalid_learning_rate"
    bad_rate["params"]["learning_rate"] = 1.1
    result.append(bad_rate)

    bad_regularizer = copy.deepcopy(base)
    bad_regularizer["name"] = "invalid_negative_regularizer"
    bad_regularizer["params"]["reg_alpha"] = -0.1
    result.append(bad_regularizer)

    return result
