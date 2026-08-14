"""Small public model construction protocol."""

from __future__ import annotations

import numpy as np


def build_case(spec):
    from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

    rng = np.random.default_rng(spec["seed"])
    X = rng.normal(size=(72, 6))
    X[:, -1] = 4.0
    signal = 1.6 * X[:, 0] - 0.75 * X[:, 1] * X[:, 2] + 0.3 * np.sin(X[:, 3])
    if spec["target"] == "regression":
        y = signal
    elif spec["target"] == "multioutput_regression":
        y = np.column_stack([signal, X[:, 2] - 0.4 * X[:, 0]])
    else:
        low, high = np.quantile(signal, [0.34, 0.68])
        y = np.where(signal < low, "alpha", np.where(signal < high, "beta", "gamma"))
    classes = {
        "decision_tree_regressor": DecisionTreeRegressor,
        "random_forest_regressor": RandomForestRegressor,
        "gradient_boosting_regressor": GradientBoostingRegressor,
        "decision_tree_classifier": DecisionTreeClassifier,
    }
    model = classes[spec["kind"]](random_state=spec["seed"] + 100, **spec["params"])
    model.fit(X, y)
    X_eval = rng.normal(size=(4, 6))
    X_eval[:, -1] = 4.0
    return model, X_eval

