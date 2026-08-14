"""Deterministic hidden MSM fixtures."""


def hidden_cases():
    return [
        {
            "name": "two_state_balanced",
            "trajectories": [[0, 0, 1, 1, 0, 1, 0, 0, 1, 1, 0]],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "two_state_asymmetric",
            "trajectories": [[0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1]],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "three_state_dense",
            "trajectories": [[0, 0, 1, 2, 2, 1, 0, 2, 1, 1, 0, 2, 2, 0]],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "lag_two_sliding",
            "trajectories": [[0, 1, 1, 2, 0, 2, 1, 0, 0, 2, 1, 2]],
            "lag": 2, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "lag_three_sample",
            "trajectories": [[0, 1, 2, 1, 0, 2, 2, 1, 0, 1, 2, 0, 0]],
            "lag": 3, "count_mode": "sample", "reversible": True,
        },
        {
            "name": "multiple_trajectories",
            "trajectories": [
                [0, 0, 1, 2, 1, 0, 2],
                [2, 2, 1, 0, 1, 2, 0],
                [1, 1, 0, 2, 2, 1],
            ],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "disconnected_equal_tie",
            "trajectories": [
                [0, 0, 1, 1, 0, 1, 0],
                [4, 4, 5, 5, 4, 5, 4],
            ],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "disconnected_larger_component",
            "trajectories": [
                [2, 2, 4, 7, 4, 2, 7, 7, 4, 2],
                [10, 10, 10, 10],
            ],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "gapped_state_labels",
            "trajectories": [[2, 2, 7, 7, 2, 7, 2, 2, 7]],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "sparse_four_state_bridge",
            "trajectories": [[0, 0, 1, 0, 2, 2, 1, 3, 3, 2, 0, 3, 1, 1]],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "four_state_lag_two",
            "trajectories": [[0, 1, 0, 2, 1, 3, 2, 0, 3, 1, 2, 3, 0, 0]],
            "lag": 2, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "periodic_pair_reversible",
            "trajectories": [[0, 1, 0, 1, 0, 1, 0, 1, 0, 1]],
            "lag": 1, "count_mode": "sliding", "reversible": True,
        },
        {
            "name": "nonreversible_pair",
            "trajectories": [[0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1]],
            "lag": 1, "count_mode": "sliding", "reversible": False,
        },
        {
            "name": "nonreversible_three_cycle",
            "trajectories": [[0, 1, 2, 0, 1, 2, 0, 2, 0, 1, 2, 1, 0, 1]],
            "lag": 1, "count_mode": "sliding", "reversible": False,
        },
        {
            "name": "multi_lag_two_nonreversible",
            "trajectories": [
                [0, 1, 2, 1, 0, 2, 2, 1, 0],
                [2, 0, 1, 1, 2, 0, 0, 1, 2],
            ],
            "lag": 2, "count_mode": "sample", "reversible": False,
        },
    ]

