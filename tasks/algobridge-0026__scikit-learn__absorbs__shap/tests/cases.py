"""Hidden deterministic differential cases for ALGOBRIDGE-0026."""

from __future__ import annotations


def _case(name, kind, target, seed, *, output=None, **kwargs):
    return {
        "name": name,
        "kind": kind,
        "target": target,
        "seed": seed,
        "output": output,
        **kwargs,
    }


def hidden_cases():
    return [
        _case(
            "weighted_tree_regression",
            "decision_tree_regressor",
            "regression",
            101,
            sample_weight=True,
            params={"max_depth": 5, "min_samples_leaf": 2},
        ),
        _case(
            "multioutput_tree_second",
            "decision_tree_regressor",
            "multioutput_regression",
            113,
            output=1,
            params={"max_depth": 6, "min_samples_leaf": 2},
        ),
        _case(
            "multioutput_tree_all",
            "decision_tree_regressor",
            "multioutput_regression",
            127,
            params={"max_depth": 4},
        ),
        _case(
            "forest_regression_order",
            "random_forest_regressor",
            "regression",
            139,
            mutation="reverse_forest",
            params={"n_estimators": 11, "max_depth": 6, "max_features": 0.8},
        ),
        _case(
            "multioutput_forest",
            "random_forest_regressor",
            "multioutput_regression",
            149,
            sample_weight=True,
            params={"n_estimators": 9, "max_depth": 5, "bootstrap": True},
        ),
        _case(
            "boosting_regression",
            "gradient_boosting_regressor",
            "regression",
            163,
            quantized=True,
            params={"n_estimators": 13, "max_depth": 3, "learning_rate": 0.17},
        ),
        _case(
            "binary_tree_string_selector",
            "decision_tree_classifier",
            "binary",
            179,
            output="positive",
            sample_weight=True,
            params={"max_depth": 5, "min_samples_leaf": 3},
        ),
        _case(
            "multiclass_tree_all",
            "decision_tree_classifier",
            "multiclass",
            191,
            params={"max_depth": 6, "min_samples_leaf": 2},
        ),
        _case(
            "multiclass_forest_beta",
            "random_forest_classifier",
            "multiclass",
            211,
            output="beta",
            params={"n_estimators": 13, "max_depth": 6, "max_features": 0.7},
        ),
        _case(
            "binary_gradient_boosting",
            "gradient_boosting_classifier",
            "binary",
            223,
            params={"n_estimators": 11, "max_depth": 2, "learning_rate": 0.21},
        ),
        _case(
            "learned_missing_branch",
            "decision_tree_regressor",
            "regression",
            239,
            missing=True,
            missing_feature=1,
            params={"max_depth": 6, "min_samples_leaf": 2},
        ),
        _case(
            "deep_repeated_thresholds",
            "decision_tree_regressor",
            "regression",
            251,
            n_train=360,
            n_features=19,
            quantized=True,
            params={"max_depth": 12, "min_samples_leaf": 1},
        ),
        _case(
            "dataframe_forest",
            "random_forest_regressor",
            "regression",
            269,
            dataframe=True,
            params={"n_estimators": 7, "max_depth": 5},
        ),
    ]


def invariant_cases():
    return [
        _case(
            "single_boosting_tree",
            "gradient_boosting_regressor",
            "regression",
            307,
            params={"n_estimators": 1, "max_depth": 4, "learning_rate": 0.3},
        ),
        _case(
            "duplicated_boosting_tree",
            "gradient_boosting_regressor",
            "regression",
            307,
            mutation="duplicate_boosting_tree",
            params={"n_estimators": 1, "max_depth": 4, "learning_rate": 0.3},
        ),
    ]

