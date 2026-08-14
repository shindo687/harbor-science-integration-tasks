"""Five deterministic public examples for ALGOBRIDGE-0027."""


def public_cases():
    return [
        {
            "name": "public_binary_auto",
            "X": [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [8.0, 8.0], [8.0, 9.0], [9.0, 8.0], [9.0, 9.0]],
            "y": [0, 0, 0, 1, 1, 1, 1],
            "strategy": {"kind": "str", "value": "auto"},
            "k_neighbors": 2,
            "random_state": 7,
            "dtype": "float64",
            "sample_weight": None,
        },
        {
            "name": "public_multiclass",
            "X": [[0.0, 0.0], [0.0, 1.0], [1.0, 0.0], [5.0, 5.0], [5.0, 6.0], [6.0, 5.0], [6.0, 6.0], [10.0, 10.0], [10.0, 11.0], [11.0, 10.0], [11.0, 11.0], [10.5, 10.5]],
            "y": [0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 2],
            "strategy": {"kind": "str", "value": "auto"},
            "k_neighbors": 2,
            "random_state": 13,
            "dtype": "float64",
            "sample_weight": None,
        },
        {
            "name": "public_target_dict",
            "X": [[-1.0, 0.0], [0.0, 1.0], [1.0, 0.0], [0.0, -1.0], [7.0, 7.0], [7.0, 8.0], [8.0, 7.0], [8.0, 8.0], [7.5, 8.5], [8.5, 7.5]],
            "y": ["rare"] * 4 + ["common"] * 6,
            "strategy": {"kind": "dict", "items": [["rare", 8]]},
            "k_neighbors": 3,
            "random_state": 19,
            "dtype": "float64",
            "sample_weight": None,
        },
        {
            "name": "public_float32",
            "X": [[0.0, 0.0, 0.0], [0.0, 1.0, 0.2], [1.0, 0.0, 0.4], [0.5, 0.5, 0.8], [9.0, 9.0, 9.0], [9.0, 10.0, 9.2], [10.0, 9.0, 9.4], [10.0, 10.0, 9.6], [9.5, 9.5, 9.8], [10.5, 9.5, 10.0], [9.5, 10.5, 10.2]],
            "y": [0] * 4 + [1] * 7,
            "strategy": {"kind": "float", "value": 1.0},
            "k_neighbors": 3,
            "random_state": 37,
            "dtype": "float32",
            "sample_weight": None,
        },
        {
            "name": "public_weight_lineage",
            "X": [[0.0, 0.0], [0.0, 2.0], [2.0, 0.0], [2.0, 2.0], [10.0, 10.0], [10.0, 11.0], [11.0, 10.0], [11.0, 11.0], [10.5, 11.5], [11.5, 10.5], [12.0, 11.0], [11.0, 12.0]],
            "y": [0] * 4 + [1] * 8,
            "strategy": {"kind": "str", "value": "auto"},
            "k_neighbors": 3,
            "random_state": 41,
            "dtype": "float64",
            "sample_weight": [0.5, 1.0, 1.5, 2.0, 1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7],
        },
    ]
