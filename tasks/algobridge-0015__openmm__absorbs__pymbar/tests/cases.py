"""Private deterministic cases for ALGOBRIDGE-0015."""

from __future__ import annotations

import numpy as np


def _case(name, centers, stiffness, counts, seed, *, sample_scale=0.7,
          state_offsets=None, initial_f_k=None, common_offset=None,
          duplicate=False):
    centers = np.asarray(centers, dtype=float)
    stiffness = np.asarray(stiffness, dtype=float)
    counts = np.asarray(counts, dtype=int)
    rng = np.random.default_rng(seed)
    pieces = []
    for center, k, count in zip(centers, stiffness, counts, strict=True):
        if count:
            values = rng.normal(center, sample_scale / np.sqrt(k), int(count))
            if duplicate and count >= 4:
                values[1::4] = values[0::4][:len(values[1::4])]
            pieces.append(values)
    positions = np.concatenate(pieces)
    return {
        "name": name,
        "centers": centers.tolist(),
        "stiffness": stiffness.tolist(),
        "state_offsets": (np.zeros_like(centers) if state_offsets is None
                          else np.asarray(state_offsets, dtype=float)).tolist(),
        "N_k": counts.tolist(),
        "positions": positions.tolist(),
        "initial_f_k": initial_f_k,
        "common_offset": common_offset,
        "relative_tolerance": 1e-12,
        "maximum_iterations": 20000,
    }


def hidden_cases():
    return [
        _case("two_state_high_overlap", [-0.25, 0.35], [1.0, 1.2], [28, 28], 1501),
        _case("two_state_low_overlap", [-2.0, 2.0], [1.6, 1.6], [36, 36], 1502,
              sample_scale=0.55),
        _case("unequal_counts", [-0.7, 0.9], [0.8, 1.7], [17, 53], 1503),
        _case("three_state_bridge", [-1.5, 0.0, 1.5], [1.4, 1.0, 1.4],
              [24, 30, 24], 1504),
        _case("unsampled_middle", [-1.2, 0.0, 1.2], [1.1, 0.9, 1.3],
              [34, 0, 34], 1505),
        _case("duplicated_samples", [-0.8, 0.4, 1.3], [1.2, 1.0, 1.4],
              [25, 25, 25], 1506, duplicate=True),
        _case("large_state_offsets", [-0.9, 0.1, 1.0], [0.9, 1.1, 1.3],
              [30, 30, 30], 1507, state_offsets=[700.0, -600.0, 250.0]),
        _case("common_sample_offsets", [-0.9, 0.1, 1.0], [0.9, 1.1, 1.3],
              [30, 30, 30], 1507, state_offsets=[700.0, -600.0, 250.0],
              common_offset="alternating_extreme"),
        _case("warm_start", [-1.0, 0.2, 1.4], [0.7, 1.5, 2.2], [29, 31, 27],
              1508, initial_f_k=[0.0, 3.0, -2.0]),
        _case("near_identical", [0.0, 1e-4], [1.0, 1.0002], [40, 40], 1509),
        _case("four_state_ladder", [-1.8, -0.6, 0.6, 1.8],
              [1.5, 1.1, 0.9, 1.3], [18, 27, 31, 22], 1510),
        _case("asymmetric_stiffness", [-0.4, 0.2, 0.8], [0.25, 2.0, 7.5],
              [45, 30, 20], 1511, sample_scale=0.8),
    ]


def invalid_cases():
    return [
        {"name": "invalid_count_sum", "u_kn": [[0.0, 1.0], [1.0, 0.0]],
         "N_k": [1, 0]},
        {"name": "invalid_negative_count", "u_kn": [[0.0, 1.0], [1.0, 0.0]],
         "N_k": [3, -1]},
        {"name": "invalid_nonfinite", "u_kn": [[0.0, None], [1.0, 0.0]],
         "N_k": [1, 1]},
    ]

