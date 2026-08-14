"""Intentionally wrong Saabas-style single-path attribution baseline."""

from __future__ import annotations

import numpy as np

from sklearn.ensemble import (
    GradientBoostingClassifier,
    GradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor
from sklearn.utils import Bunch
from sklearn.utils.validation import check_is_fitted, validate_data


def _trees(model):
    classifier = isinstance(model, (DecisionTreeClassifier, RandomForestClassifier))
    if hasattr(model, "tree_"):
        items, scale = [model], 1.0
    elif isinstance(model, (RandomForestRegressor, RandomForestClassifier)):
        items, scale = model.estimators_, 1.0 / len(model.estimators_)
    else:
        items, scale = model.estimators_[:, 0], model.learning_rate
    for item in items:
        tree = item.tree_
        values = np.asarray(tree.value).reshape(tree.node_count, -1).astype(float)
        if classifier:
            values /= values.sum(axis=1, keepdims=True)
        yield tree, values * scale


def tree_shap(estimator, X, *, output=None, check_additivity=True):
    """Approximate path-dependent attributions using one decision path only."""
    check_is_fitted(estimator)
    supported = (
        DecisionTreeRegressor,
        DecisionTreeClassifier,
        RandomForestRegressor,
        RandomForestClassifier,
        GradientBoostingRegressor,
        GradientBoostingClassifier,
    )
    if not isinstance(estimator, supported):
        raise TypeError("unsupported estimator")
    if getattr(estimator, "is_categorical_", None) is not None:
        raise ValueError("categorical tree splits are not supported")
    X = validate_data(estimator, X, dtype=np.float32, reset=False, ensure_all_finite="allow-nan")
    models = list(_trees(estimator))
    values = np.zeros((len(X), X.shape[1], models[0][1].shape[1]))
    base = sum((node_values[0] for _, node_values in models), start=np.zeros(values.shape[2]))
    for tree, node_values in models:
        for row_index, row in enumerate(X):
            node = 0
            while tree.children_left[node] >= 0:
                feature = int(tree.feature[node])
                if np.isnan(row[feature]):
                    child = tree.children_left[node] if tree.missing_go_to_left[node] else tree.children_right[node]
                else:
                    child = tree.children_left[node] if row[feature] <= tree.threshold[node] else tree.children_right[node]
                values[row_index, feature] += node_values[child] - node_values[node]
                node = int(child)
    if isinstance(estimator, GradientBoostingClassifier):
        predictions = np.asarray(estimator.decision_function(X))
    elif isinstance(estimator, (DecisionTreeClassifier, RandomForestClassifier)):
        predictions = np.asarray(estimator.predict_proba(X))
    else:
        predictions = np.asarray(estimator.predict(X))
    if isinstance(estimator, (GradientBoostingRegressor, GradientBoostingClassifier)):
        prediction_matrix = predictions.reshape(-1, values.shape[2])
        base += np.mean(prediction_matrix - (base + values.sum(axis=1)), axis=0)
    if values.shape[2] == 1:
        if output not in (None, 0, -1):
            raise IndexError("invalid output")
        values, base, predictions = values[:, :, 0], float(base[0]), predictions.reshape(-1)
    elif output is not None:
        if isinstance(output, str):
            matches = np.flatnonzero(estimator.classes_ == output)
            if len(matches) != 1:
                raise ValueError("unknown output")
            output = int(matches[0])
        values, base, predictions = values[:, :, output], float(base[output]), predictions[:, output]
    return Bunch(values=values, base_values=base, predictions=predictions)
