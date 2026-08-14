"""Deterministic hidden dense-array fixtures for ALGOBRIDGE-0027."""

from __future__ import annotations


def _cluster(count, center, dimensions=3, scale=0.17):
    rows = []
    for index in range(count):
        rows.append(
            [
                center
                + scale * (((index + 2 * feature) % (count + 2)) - count / 3)
                + 0.011 * index * feature
                for feature in range(dimensions)
            ]
        )
    return rows


def _case(
    name,
    X,
    y,
    strategy,
    *,
    k_neighbors,
    random_state,
    dtype="float64",
    sample_weight=None,
):
    return {
        "name": name,
        "X": X,
        "y": y,
        "strategy": strategy,
        "k_neighbors": k_neighbors,
        "random_state": random_state,
        "dtype": dtype,
        "sample_weight": sample_weight,
    }


def hidden_cases():
    cases = []
    cases.append(
        _case(
            "binary_auto",
            _cluster(4, 0.0, 2) + _cluster(7, 8.0, 2),
            [0] * 4 + [1] * 7,
            {"kind": "str", "value": "auto"},
            k_neighbors=3,
            random_state=17,
        )
    )
    cases.append(
        _case(
            "multiclass_auto",
            _cluster(4, -5.0) + _cluster(6, 1.0) + _cluster(8, 7.0),
            [0] * 4 + [1] * 6 + [2] * 8,
            {"kind": "str", "value": "auto"},
            k_neighbors=2,
            random_state=31,
        )
    )
    cases.append(
        _case(
            "binary_dict",
            _cluster(7, -2.0, 4) + _cluster(4, 4.0, 4),
            [-1] * 7 + [3] * 4,
            {"kind": "dict", "items": [[3, 9]]},
            k_neighbors=3,
            random_state=9,
        )
    )
    cases.append(
        _case(
            "multiclass_dict",
            _cluster(4, -9.0, 2) + _cluster(9, 0.0, 2) + _cluster(5, 9.0, 2),
            [0] * 4 + [1] * 9 + [2] * 5,
            {"kind": "dict", "items": [[0, 8], [2, 7]]},
            k_neighbors=3,
            random_state=101,
        )
    )
    cases.append(
        _case(
            "string_labels",
            _cluster(4, 0.0, 2) + _cluster(7, 6.0, 2),
            ["minor"] * 4 + ["major"] * 7,
            {"kind": "str", "value": "minority"},
            k_neighbors=2,
            random_state=23,
        )
    )
    cases.append(
        _case(
            "duplicate_points",
            [[0.0, 0.0], [0.0, 0.0], [1.0, 0.0], [0.0, 1.0]]
            + _cluster(8, 12.0, 2),
            [0] * 4 + [1] * 8,
            {"kind": "str", "value": "auto"},
            k_neighbors=2,
            random_state=5,
        )
    )
    cases.append(
        _case(
            "equidistant_ties",
            [[0.0, 0.0], [1.0, 0.0], [-1.0, 0.0], [0.0, 1.0], [0.0, -1.0]]
            + _cluster(9, 15.0, 2),
            [2] * 5 + [8] * 9,
            {"kind": "str", "value": "auto"},
            k_neighbors=3,
            random_state=77,
        )
    )
    cases.append(
        _case(
            "float32",
            _cluster(5, -3.0, 5, 0.09) + _cluster(9, 5.0, 5, 0.13),
            [0] * 5 + [1] * 9,
            {"kind": "str", "value": "auto"},
            k_neighbors=4,
            random_state=43,
            dtype="float32",
        )
    )
    weighted_X = _cluster(4, -1.0, 3) + _cluster(8, 10.0, 3)
    cases.append(
        _case(
            "sample_weight_lineage",
            weighted_X,
            [0] * 4 + [1] * 8,
            {"kind": "str", "value": "auto"},
            k_neighbors=3,
            random_state=29,
            sample_weight=[0.2, 0.7, 1.1, 2.0]
            + [1.0 + 0.25 * index for index in range(8)],
        )
    )
    cases.append(
        _case(
            "binary_float_ratio",
            _cluster(4, 0.0, 2) + _cluster(10, 20.0, 2),
            [0] * 4 + [1] * 10,
            {"kind": "float", "value": 0.7},
            k_neighbors=3,
            random_state=123,
        )
    )
    cases.append(
        _case(
            "all_classes",
            _cluster(4, -8.0, 2) + _cluster(6, 0.0, 2) + _cluster(7, 8.0, 2),
            [0] * 4 + [1] * 6 + [2] * 7,
            {"kind": "str", "value": "all"},
            k_neighbors=3,
            random_state=61,
        )
    )
    cases.append(
        _case(
            "high_dimensional",
            _cluster(5, -4.0, 11, 0.07) + _cluster(11, 4.0, 11, 0.08),
            [0] * 5 + [1] * 11,
            {"kind": "dict", "items": [[0, 12]]},
            k_neighbors=4,
            random_state=997,
            sample_weight=[0.5 + 0.1 * index for index in range(16)],
        )
    )
    return cases
