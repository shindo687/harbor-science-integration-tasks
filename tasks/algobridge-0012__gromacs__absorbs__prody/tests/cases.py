"""Deterministic hidden coordinate networks for GROMACS ANM fitting."""

from __future__ import annotations

import math

import numpy as np


def item(name, coordinates, *, cutoff_nm=1.5, gamma=1.0, n_modes=20,
         selection=None):
    return {
        "name": name,
        "coordinates_nm": np.asarray(coordinates, dtype=float).tolist(),
        "arguments": {
            "selection": None if selection is None else list(selection),
            "cutoff_nm": float(cutoff_nm),
            "gamma": float(gamma),
            "n_modes": int(n_modes),
        },
    }


TETRAHEDRON = np.array([
    [0.00, 0.00, 0.00],
    [0.52, 0.00, 0.00],
    [0.17, 0.61, 0.00],
    [0.11, 0.22, 0.73],
])

IRREGULAR = np.array([
    [0.00, 0.00, 0.00],
    [0.48, 0.05, 0.02],
    [0.16, 0.57, 0.09],
    [0.08, 0.18, 0.67],
    [0.61, 0.49, 0.38],
    [0.86, 0.13, 0.52],
    [0.34, 0.82, 0.71],
    [0.93, 0.69, 0.16],
])


def helix(count=8):
    index = np.arange(count, dtype=float)
    angle = 1.08 * index
    return np.column_stack([
        0.43 * np.cos(angle),
        0.43 * np.sin(angle),
        0.22 * index,
    ])


def planar_grid():
    return np.array([
        [0.42 * x, 0.42 * y, 0.0]
        for y in range(3)
        for x in range(3)
    ])


def transformed_pair():
    base = IRREGULAR.copy()
    axis = np.array([0.3, -0.7, 0.5], dtype=float)
    axis /= np.linalg.norm(axis)
    angle = 0.71
    cross = np.array([
        [0.0, -axis[2], axis[1]],
        [axis[2], 0.0, -axis[0]],
        [-axis[1], axis[0], 0.0],
    ])
    rotation = (
        np.eye(3) * math.cos(angle)
        + (1.0 - math.cos(angle)) * np.outer(axis, axis)
        + math.sin(angle) * cross
    )
    moved = base @ rotation.T + np.array([2.4, -1.7, 0.9])
    return base, moved, rotation


def permutation_pair():
    coordinates = np.array([
        [0.03, 0.04, 0.02],
        [0.51, 0.08, 0.11],
        [0.14, 0.62, 0.16],
        [0.09, 0.21, 0.74],
        [0.67, 0.53, 0.46],
        [0.88, 0.19, 0.58],
        [0.38, 0.86, 0.76],
    ])
    order = np.array([4, 0, 6, 2, 5, 1, 3])
    return coordinates, coordinates[order], order


def hidden_cases():
    rigid_base, rigid_moved, _ = transformed_pair()
    permutation_base, permutation_swapped, _ = permutation_pair()
    two_components = np.vstack([
        TETRAHEDRON,
        TETRAHEDRON + np.array([4.0, 0.2, -0.1]),
    ])
    cutoff_boundary = np.array([
        [0.00, 0.00, 0.00],
        [0.80, 0.00, 0.00],
        [0.40, 0.50, 0.00],
        [0.40, 0.18, 0.62],
        [1.18, 0.47, 0.08],
        [1.17, 0.20, 0.65],
    ])
    octahedron = np.array([
        [0.5, 0.0, 0.0], [-0.5, 0.0, 0.0],
        [0.0, 0.5, 0.0], [0.0, -0.5, 0.0],
        [0.0, 0.0, 0.5], [0.0, 0.0, -0.5],
    ])
    full_selection = np.vstack([
        IRREGULAR,
        [[1.8, -0.5, 0.4], [-0.7, 1.6, -0.2]],
    ])
    return [
        item("tetrahedron_all_modes", TETRAHEDRON,
             cutoff_nm=1.2, n_modes=20),
        item("irregular_six_subset", IRREGULAR[:6],
             cutoff_nm=1.05, n_modes=7),
        item("helical_chain", helix(), cutoff_nm=0.82, n_modes=9),
        item("linear_extra_zero_modes",
             [[0.35 * index, 0.0, 0.0] for index in range(6)],
             cutoff_nm=0.41, n_modes=20),
        item("two_disconnected_tetrahedra", two_components,
             cutoff_nm=1.2, n_modes=12),
        item("inclusive_cutoff_boundary", cutoff_boundary,
             cutoff_nm=0.8, n_modes=7),
        item("octahedral_degeneracy", octahedron,
             cutoff_nm=0.72, n_modes=20),
        item("planar_grid", planar_grid(), cutoff_nm=0.61, n_modes=30),
        item("gamma_scaling_base", IRREGULAR[:7],
             cutoff_nm=1.05, gamma=0.7, n_modes=8),
        item("gamma_scaling_tripled", IRREGULAR[:7],
             cutoff_nm=1.05, gamma=2.1, n_modes=8),
        item("rigid_transform_base", rigid_base,
             cutoff_nm=1.05, gamma=1.3, n_modes=8),
        item("rigid_transform_moved", rigid_moved,
             cutoff_nm=1.05, gamma=1.3, n_modes=8),
        item("atom_permutation_base", permutation_base,
             cutoff_nm=1.05, gamma=0.9, n_modes=8),
        item("atom_permutation_swapped", permutation_swapped,
             cutoff_nm=1.05, gamma=0.9, n_modes=8),
        item("ordered_selection", full_selection,
             selection=[7, 2, 5, 0, 4, 6], cutoff_nm=1.05,
             gamma=1.1, n_modes=7),
    ]


__all__ = [
    "IRREGULAR", "TETRAHEDRON", "hidden_cases", "item", "helix",
    "permutation_pair", "planar_grid", "transformed_pair",
]
