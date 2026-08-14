"""Exact path-dependent SHAP values for fitted sklearn binary trees."""

# Authors: The scikit-learn developers
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from numbers import Integral

import numpy as np
from scipy import sparse

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.utils import Bunch
from sklearn.utils.validation import check_is_fitted, validate_data


_SINGLE_TREES = (DecisionTreeRegressor, DecisionTreeClassifier)
_FORESTS = (RandomForestRegressor, RandomForestClassifier)
_BOOSTING = (GradientBoostingRegressor, GradientBoostingClassifier)
_SUPPORTED = _SINGLE_TREES + _FORESTS + _BOOSTING


def _extend_path(feature, zero, one, weight, depth, zero_fraction, one_fraction, feature_index):
    feature[depth] = feature_index
    zero[depth] = zero_fraction
    one[depth] = one_fraction
    weight[depth] = 1.0 if depth == 0 else 0.0
    for index in range(depth - 1, -1, -1):
        weight[index + 1] += one_fraction * weight[index] * (index + 1.0) / (depth + 1.0)
        weight[index] = zero_fraction * weight[index] * (depth - index) / (depth + 1.0)


def _unwind_path(feature, zero, one, weight, depth, path_index):
    one_fraction = one[path_index]
    zero_fraction = zero[path_index]
    next_one_portion = weight[depth]
    for index in range(depth - 1, -1, -1):
        if one_fraction != 0.0:
            temporary = weight[index]
            weight[index] = next_one_portion * (depth + 1.0) / ((index + 1.0) * one_fraction)
            next_one_portion = temporary - weight[index] * zero_fraction * (depth - index) / (depth + 1.0)
        elif zero_fraction != 0.0:
            weight[index] = weight[index] * (depth + 1.0) / (zero_fraction * (depth - index))
    for index in range(path_index, depth):
        feature[index] = feature[index + 1]
        zero[index] = zero[index + 1]
        one[index] = one[index + 1]


def _unwound_path_sum(zero, one, weight, depth, path_index):
    one_fraction = one[path_index]
    zero_fraction = zero[path_index]
    next_one_portion = weight[depth]
    total = 0.0
    for index in range(depth - 1, -1, -1):
        if one_fraction != 0.0:
            temporary = next_one_portion * (depth + 1.0) / ((index + 1.0) * one_fraction)
            total += temporary
            next_one_portion = weight[index] - temporary * zero_fraction * (depth - index) / (depth + 1.0)
        elif zero_fraction != 0.0:
            total += weight[index] * (depth + 1.0) / (zero_fraction * (depth - index))
    return total


def _recurse(tree, values, x, missing, output, node, depth, feature, zero, one, weight,
             parent_zero, parent_one, parent_feature):
    # Each recursive branch owns its path storage, which avoids aliasing between
    # the hot and cold branches while preserving the polynomial path algorithm.
    feature = feature.copy()
    zero = zero.copy()
    one = one.copy()
    weight = weight.copy()
    _extend_path(feature, zero, one, weight, depth, parent_zero, parent_one, parent_feature)

    left = int(tree.children_left[node])
    right = int(tree.children_right[node])
    if left < 0:
        for path_index in range(1, depth + 1):
            contribution = _unwound_path_sum(zero, one, weight, depth, path_index)
            output[feature[path_index]] += contribution * (
                one[path_index] - zero[path_index]
            ) * values[node]
        return

    split_feature = int(tree.feature[node])
    if missing[split_feature]:
        default_left = bool(tree.missing_go_to_left[node]) if hasattr(tree, "missing_go_to_left") else True
        hot = left if default_left else right
    else:
        hot = left if x[split_feature] <= tree.threshold[node] else right
    cold = right if hot == left else left
    node_weight = float(tree.weighted_n_node_samples[node])
    if node_weight <= 0.0:
        raise ValueError("tree contains a node with nonpositive weighted cover")
    hot_zero = float(tree.weighted_n_node_samples[hot]) / node_weight
    cold_zero = float(tree.weighted_n_node_samples[cold]) / node_weight

    incoming_zero = 1.0
    incoming_one = 1.0
    path_index = 0
    while path_index <= depth:
        if feature[path_index] == split_feature:
            incoming_zero = zero[path_index]
            incoming_one = one[path_index]
            _unwind_path(feature, zero, one, weight, depth, path_index)
            depth -= 1
            break
        path_index += 1

    _recurse(
        tree, values, x, missing, output, hot, depth + 1, feature, zero, one, weight,
        hot_zero * incoming_zero, incoming_one, split_feature,
    )
    _recurse(
        tree, values, x, missing, output, cold, depth + 1, feature, zero, one, weight,
        cold_zero * incoming_zero, 0.0, split_feature,
    )


def _tree_values(tree, *, normalize, scale):
    values = np.asarray(tree.value, dtype=float).reshape(tree.node_count, -1)
    if normalize:
        totals = values.sum(axis=1, keepdims=True)
        values = np.divide(values, totals, out=np.zeros_like(values), where=totals != 0.0)
    return values * scale


def _models(estimator):
    normalize = isinstance(estimator, (DecisionTreeClassifier, RandomForestClassifier))
    if isinstance(estimator, _SINGLE_TREES):
        yield estimator.tree_, _tree_values(estimator.tree_, normalize=normalize, scale=1.0)
    elif isinstance(estimator, _FORESTS):
        scale = 1.0 / len(estimator.estimators_)
        for fitted_tree in estimator.estimators_:
            yield fitted_tree.tree_, _tree_values(fitted_tree.tree_, normalize=normalize, scale=scale)
    else:
        if estimator.estimators_.shape[1] != 1:
            raise ValueError("multiclass GradientBoostingClassifier is not supported")
        for fitted_tree in estimator.estimators_[:, 0]:
            yield fitted_tree.tree_, _tree_values(
                fitted_tree.tree_, normalize=False, scale=estimator.learning_rate
            )


def _validate_estimator(estimator):
    if not isinstance(estimator, _SUPPORTED):
        raise TypeError(
            "estimator must be a supported fitted DecisionTree, RandomForest, "
            "or GradientBoosting estimator"
        )
    check_is_fitted(estimator)
    if getattr(estimator, "is_categorical_", None) is not None:
        raise ValueError("categorical tree splits are not supported")
    if isinstance(estimator, (DecisionTreeClassifier, RandomForestClassifier)) and estimator.n_outputs_ != 1:
        raise ValueError("multi-output classification is not supported")
    if isinstance(estimator, GradientBoostingClassifier) and estimator.n_classes_ != 2:
        raise ValueError("only binary GradientBoostingClassifier is supported")
    if isinstance(estimator, _BOOSTING) and getattr(estimator, "init", None) == "zero":
        return
    if isinstance(estimator, _BOOSTING) and not hasattr(estimator.init_, "constant_") and not hasattr(estimator.init_, "class_prior_"):
        raise ValueError("custom GradientBoosting init estimators are not supported")


def _validate_X(estimator, X):
    if sparse.issparse(X):
        raise TypeError("sparse input is not supported")
    first_tree = next(_models(estimator))[0]
    allow_nan = hasattr(first_tree, "missing_go_to_left")
    return validate_data(
        estimator,
        X,
        dtype=np.float32,
        order="C",
        accept_sparse=False,
        reset=False,
        ensure_all_finite="allow-nan" if allow_nan else True,
    )


def _raw_predictions(estimator, X):
    if isinstance(estimator, GradientBoostingClassifier):
        return np.asarray(estimator.decision_function(X), dtype=float)
    if isinstance(estimator, (DecisionTreeClassifier, RandomForestClassifier)):
        return np.asarray(estimator.predict_proba(X), dtype=float)
    return np.asarray(estimator.predict(X), dtype=float)


def _select_output(estimator, output, values, base_values, predictions):
    if values.shape[2] == 1:
        if output not in (None, 0, -1):
            raise IndexError("single-output estimator only has output 0")
        return values[:, :, 0], float(base_values[0]), predictions.reshape(-1)
    if output is None:
        return values, base_values, predictions
    if isinstance(output, Integral) and not isinstance(output, (bool, np.bool_)):
        index = int(output)
        if index < 0:
            index += values.shape[2]
    else:
        classes = np.asarray(estimator.classes_, dtype=object)
        matches = np.flatnonzero(classes == output)
        if len(matches) != 1:
            raise ValueError(f"unknown class selector: {output!r}")
        index = int(matches[0])
    if index < 0 or index >= values.shape[2]:
        raise IndexError("output selector is out of range")
    return values[:, :, index], float(base_values[index]), predictions[:, index]


def tree_shap(estimator, X, *, output=None, check_additivity=True):
    """Compute exact path-dependent TreeSHAP values.

    The fitted tree's weighted node covers define the background distribution.
    The returned :class:`~sklearn.utils.Bunch` contains ``values``,
    ``base_values``, and raw ``predictions``.
    """
    _validate_estimator(estimator)
    X_array = _validate_X(estimator, X)
    model_trees = list(_models(estimator))
    n_outputs = model_trees[0][1].shape[1]
    values = np.zeros((X_array.shape[0], X_array.shape[1], n_outputs), dtype=float)
    base_values = np.zeros(n_outputs, dtype=float)
    for tree, tree_values in model_trees:
        base_values += tree_values[0]
        path_size = max(2 * int(tree.max_depth) + 4, 4)
        for row_index, row in enumerate(X_array):
            output_values = np.zeros((X_array.shape[1], n_outputs), dtype=float)
            _recurse(
                tree,
                tree_values,
                row,
                np.isnan(row),
                output_values,
                0,
                0,
                np.full(path_size, -1, dtype=np.intp),
                np.zeros(path_size, dtype=float),
                np.zeros(path_size, dtype=float),
                np.zeros(path_size, dtype=float),
                1.0,
                1.0,
                -1,
            )
            values[row_index] += output_values

    predictions = _raw_predictions(estimator, X)
    if isinstance(estimator, _BOOSTING):
        # Tree roots account only for the fitted stages. Recover the exact
        # constant initial raw value from the model output.
        tree_predictions = base_values + values.sum(axis=1)
        prediction_matrix = predictions.reshape(-1, n_outputs)
        base_values += np.mean(prediction_matrix - tree_predictions, axis=0)

    values, base_values, predictions = _select_output(
        estimator, output, values, base_values, predictions
    )
    if check_additivity:
        reconstruction = values.sum(axis=1) + base_values
        if not np.allclose(reconstruction, predictions, rtol=1e-7, atol=1e-7):
            error = float(np.max(np.abs(reconstruction - predictions)))
            raise RuntimeError(f"TreeSHAP additivity check failed (max error={error:.3g})")
    return Bunch(values=values, base_values=base_values, predictions=predictions)
