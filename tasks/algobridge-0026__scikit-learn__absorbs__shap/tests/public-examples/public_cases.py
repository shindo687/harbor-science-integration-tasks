"""Five deterministic public TreeSHAP examples."""


def public_cases():
    return [
        {
            "name": "public_tree_regression",
            "kind": "decision_tree_regressor",
            "target": "regression",
            "seed": 11,
            "output": None,
            "params": {"max_depth": 4, "min_samples_leaf": 2},
        },
        {
            "name": "public_multioutput_tree",
            "kind": "decision_tree_regressor",
            "target": "multioutput_regression",
            "seed": 23,
            "output": None,
            "params": {"max_depth": 4},
        },
        {
            "name": "public_forest_regression",
            "kind": "random_forest_regressor",
            "target": "regression",
            "seed": 37,
            "output": None,
            "params": {"n_estimators": 5, "max_depth": 4},
        },
        {
            "name": "public_multiclass_tree",
            "kind": "decision_tree_classifier",
            "target": "multiclass",
            "seed": 41,
            "output": "beta",
            "params": {"max_depth": 5, "min_samples_leaf": 2},
        },
        {
            "name": "public_boosting_regression",
            "kind": "gradient_boosting_regressor",
            "target": "regression",
            "seed": 53,
            "output": None,
            "params": {"n_estimators": 7, "max_depth": 2, "learning_rate": 0.2},
        },
    ]

