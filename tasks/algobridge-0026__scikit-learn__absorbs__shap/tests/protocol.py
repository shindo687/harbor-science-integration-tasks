"""Shared, non-secret model construction and result normalization protocol."""

from __future__ import annotations

import copy

import numpy as np


def build_case(spec):
    """Train the deterministic sklearn model described by *spec*."""
    from sklearn.ensemble import (
        GradientBoostingClassifier,
        GradientBoostingRegressor,
        RandomForestClassifier,
        RandomForestRegressor,
    )
    from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor

    rng = np.random.default_rng(int(spec["seed"]))
    n_train = int(spec.get("n_train", 120))
    n_features = int(spec.get("n_features", 7))
    X = rng.normal(size=(n_train, n_features))
    if spec.get("quantized"):
        X[:, :4] = np.round(X[:, :4], 1)
    X[:, -1] = 2.75  # a guaranteed globally unused feature

    signal = (
        1.8 * X[:, 0]
        - 0.9 * X[:, 1] * X[:, 2]
        + 0.45 * np.sin(2.2 * X[:, 3])
        + 0.25 * (X[:, 4] > 0)
    )
    target_kind = spec["target"]
    if target_kind == "regression":
        y = signal + 0.04 * rng.normal(size=n_train)
    elif target_kind == "multioutput_regression":
        y = np.column_stack(
            [signal, -0.4 * signal + 1.2 * X[:, 2] - 0.35 * X[:, 0] ** 2]
        )
    elif target_kind == "binary":
        y = np.where(signal >= np.median(signal), "positive", "negative")
    elif target_kind == "multiclass":
        lower, upper = np.quantile(signal, [0.34, 0.68])
        y = np.where(signal < lower, "alpha", np.where(signal < upper, "beta", "gamma"))
    else:
        raise ValueError(f"unknown target kind: {target_kind}")

    if spec.get("missing"):
        missing_rows = np.arange(0, n_train, 7)
        X[missing_rows, int(spec.get("missing_feature", 1))] = np.nan

    params = dict(spec.get("params", {}))
    params.setdefault("random_state", int(spec["seed"]) + 1000)
    kind = spec["kind"]
    constructors = {
        "decision_tree_regressor": DecisionTreeRegressor,
        "random_forest_regressor": RandomForestRegressor,
        "gradient_boosting_regressor": GradientBoostingRegressor,
        "decision_tree_classifier": DecisionTreeClassifier,
        "random_forest_classifier": RandomForestClassifier,
        "gradient_boosting_classifier": GradientBoostingClassifier,
    }
    estimator = constructors[kind](**params)
    fit_X = X
    columns = [f"feature_{index}" for index in range(n_features)]
    if spec.get("dataframe"):
        import pandas as pd

        fit_X = pd.DataFrame(X, columns=columns)
    fit_kwargs = {}
    if spec.get("sample_weight"):
        fit_kwargs["sample_weight"] = 0.25 + (np.arange(n_train) % 11) / 5.0
    estimator.fit(fit_X, y, **fit_kwargs)

    eval_count = int(spec.get("n_eval", 9))
    X_eval = rng.normal(size=(eval_count, n_features))
    X_eval[:, -1] = 2.75
    if spec.get("quantized"):
        X_eval[:, :4] = np.round(X_eval[:, :4], 1)
    if spec.get("missing"):
        X_eval[::3, int(spec.get("missing_feature", 1))] = np.nan
    if spec.get("dataframe"):
        import pandas as pd

        X_eval = pd.DataFrame(X_eval, columns=columns)

    mutation = spec.get("mutation")
    if mutation == "duplicate_boosting_tree":
        if estimator.estimators_.shape != (1, 1):
            raise ValueError("duplicate mutation requires one boosting tree")
        duplicate = copy.deepcopy(estimator.estimators_[0, 0])
        estimator.estimators_ = np.asarray(
            [[estimator.estimators_[0, 0]], [duplicate]], dtype=object
        )
        estimator.n_estimators_ = 2
        estimator.n_estimators = 2
    elif mutation == "reverse_forest":
        estimator.estimators_ = list(reversed(estimator.estimators_))
    elif mutation is not None:
        raise ValueError(f"unknown mutation: {mutation}")

    return estimator, X_eval


def raw_predictions(estimator, X):
    """Return the raw output space used by the task contract."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.tree import DecisionTreeClassifier
    from sklearn.ensemble import RandomForestClassifier

    if isinstance(estimator, GradientBoostingClassifier):
        return np.asarray(estimator.decision_function(X), dtype=float)
    if isinstance(estimator, (DecisionTreeClassifier, RandomForestClassifier)):
        return np.asarray(estimator.predict_proba(X), dtype=float)
    return np.asarray(estimator.predict(X), dtype=float)


def output_index(estimator, selector, n_outputs):
    if selector is None:
        return None
    if isinstance(selector, bool):
        raise ValueError("boolean is not a valid output selector")
    if isinstance(selector, int):
        index = selector
    else:
        classes = getattr(estimator, "classes_", None)
        if classes is None:
            raise ValueError("non-integer selectors require a classifier")
        matches = np.flatnonzero(np.asarray(classes, dtype=object) == selector)
        if len(matches) != 1:
            raise ValueError(f"unknown class selector: {selector!r}")
        index = int(matches[0])
    if index < 0:
        index += n_outputs
    if index < 0 or index >= n_outputs:
        raise IndexError("output selector is out of range")
    return index


def normalize_reference(estimator, values, base_values, predictions, selector):
    values = np.asarray(values, dtype=float)
    predictions = np.asarray(predictions, dtype=float)
    if values.ndim == 2:
        base = float(np.asarray(base_values, dtype=float).reshape(-1)[0])
        if selector not in (None, 0, -1):
            raise IndexError("single-output model only has output 0")
        return values, base, predictions.reshape(-1)

    base = np.asarray(base_values, dtype=float).reshape(-1)
    index = output_index(estimator, selector, values.shape[2])
    if index is not None:
        return values[:, :, index], float(base[index]), predictions[:, index]
    return values, base, predictions


def tree_arrays(estimator):
    """Yield underlying sklearn Tree objects in prediction order."""
    from sklearn.ensemble import (
        GradientBoostingClassifier,
        GradientBoostingRegressor,
        RandomForestClassifier,
        RandomForestRegressor,
    )

    if hasattr(estimator, "tree_"):
        yield estimator.tree_
    elif isinstance(estimator, (RandomForestRegressor, RandomForestClassifier)):
        for tree in estimator.estimators_:
            yield tree.tree_
    elif isinstance(estimator, (GradientBoostingRegressor, GradientBoostingClassifier)):
        for tree in estimator.estimators_[:, 0]:
            yield tree.tree_


def used_features(estimator):
    used = set()
    for tree in tree_arrays(estimator):
        used.update(int(feature) for feature in tree.feature if int(feature) >= 0)
    return sorted(used)

