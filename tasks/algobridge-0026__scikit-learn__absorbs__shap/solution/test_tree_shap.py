"""Focused public API tests for exact path-dependent tree attributions."""

import numpy as np
import pytest

from sklearn.ensemble import RandomForestRegressor
from sklearn.inspection import tree_shap
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor


def test_tree_shap_regression_local_accuracy_and_unused_feature():
    X = np.asarray(
        [[-2.0, 0.0, 7.0], [-1.0, 1.0, 7.0], [1.0, -1.0, 7.0], [2.0, 2.0, 7.0]]
    )
    y = np.asarray([-2.0, -0.5, 1.5, 3.0])
    model = DecisionTreeRegressor(max_depth=3, random_state=0).fit(X, y)
    result = tree_shap(model, X)
    assert result["values"].shape == X.shape
    np.testing.assert_allclose(
        result["base_values"] + result["values"].sum(axis=1), model.predict(X)
    )
    assert np.array_equal(result["values"][:, 2], np.zeros(len(X)))


def test_tree_shap_classifier_output_selector():
    X = np.asarray([[-2.0, 0.0], [-1.0, 1.0], [1.0, -1.0], [2.0, 2.0]])
    y = np.asarray(["left", "left", "right", "right"])
    model = DecisionTreeClassifier(max_depth=2, random_state=0).fit(X, y)
    result = tree_shap(model, X, output="right")
    expected = model.predict_proba(X)[:, np.flatnonzero(model.classes_ == "right")[0]]
    np.testing.assert_allclose(
        result["base_values"] + result["values"].sum(axis=1), expected
    )


def test_tree_shap_forest_is_deterministic():
    rng = np.random.default_rng(4)
    X = rng.normal(size=(50, 5))
    model = RandomForestRegressor(n_estimators=5, max_depth=4, random_state=2).fit(
        X, X[:, 0] - X[:, 1] * X[:, 2]
    )
    first = tree_shap(model, X[:4])
    second = tree_shap(model, X[:4])
    assert np.array_equal(first["values"], second["values"])


def test_tree_shap_rejects_categorical_splits():
    X = np.asarray([[0.0, -1.0], [1.0, 0.0], [2.0, 1.0], [0.0, 2.0]])
    y = np.asarray([0.0, 1.0, 2.0, 0.5])
    model = DecisionTreeRegressor(
        categorical_features=[0], max_depth=2, random_state=0
    ).fit(X, y)
    with pytest.raises(ValueError, match="categorical tree splits"):
        tree_shap(model, X)
