"""Deterministic hidden FC3 fitting cases."""

from __future__ import annotations

import math

import numpy as np

from model import polynomial_design


def cell(symbols, lattice, positions):
    return {
        "symbols": list(symbols),
        "cell": np.asarray(lattice, dtype=float).tolist(),
        "scaled_positions": np.asarray(positions, dtype=float).tolist(),
    }


P1_TWO = cell(
    ["Si", "O"],
    [[5.1, 0.2, 0.1], [0.3, 5.7, 0.4], [0.2, 0.5, 6.3]],
    [[0.07, 0.13, 0.19], [0.43, 0.37, 0.31]],
)
P1_THREE = cell(
    ["Si", "O", "Cl"],
    [[5.3, 0.3, 0.2], [0.4, 6.1, 0.5], [0.1, 0.6, 6.7]],
    [[0.07, 0.13, 0.19], [0.43, 0.37, 0.31], [0.71, 0.61, 0.53]],
)
P1_FOUR = cell(
    ["Si", "O", "Cl", "Na"],
    [[6.2, 0.4, 0.2], [0.3, 6.8, 0.5], [0.2, 0.7, 7.3]],
    [[0.04, 0.11, 0.17], [0.29, 0.37, 0.23],
     [0.58, 0.49, 0.64], [0.81, 0.73, 0.42]],
)


def zincblende():
    length = 5.5
    return cell(
        ["Ga", "As"],
        [[0, length / 2, length / 2],
         [length / 2, 0, length / 2],
         [length / 2, length / 2, 0]],
        [[0, 0, 0], [0.25, 0.25, 0.25]],
    )


def rocksalt():
    length = 5.7
    return cell(
        ["Na", "Cl"],
        [[0, length / 2, length / 2],
         [length / 2, 0, length / 2],
         [length / 2, length / 2, 0]],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    )


def wurtzite():
    a, c, internal = 3.25, 5.21, 0.381
    return cell(
        ["Zn", "Zn", "O", "O"],
        [[a, 0, 0], [-a / 2, math.sqrt(3) * a / 2, 0], [0, 0, c]],
        [[1 / 3, 2 / 3, 0], [2 / 3, 1 / 3, 0.5],
         [1 / 3, 2 / 3, internal], [2 / 3, 1 / 3, 0.5 + internal]],
    )


def generated(name, structure, snapshots, seed, *, is_symmetry=False,
              amplitude=0.04, noise=0.0, duplicate=False,
              force_drift=0.0, compare_tensor=True):
    rng = np.random.default_rng(seed)
    n_atoms = len(structure["symbols"])
    displacements = rng.normal(
        scale=amplitude, size=(snapshots, n_atoms, 3)
    )
    design = polynomial_design(displacements)
    n_relative = 3 * (n_atoms - 1)
    pair_count = n_relative * (n_relative + 1) // 2
    coefficients = rng.normal(size=design.shape[1])
    coefficients[:pair_count] *= 2.5
    coefficients[pair_count:] *= 12.0
    forces = (design @ coefficients).reshape(snapshots, n_atoms, 3)
    if noise:
        perturbation = rng.normal(scale=noise, size=forces.shape)
        perturbation -= perturbation.mean(axis=1, keepdims=True)
        forces += perturbation
    if force_drift:
        forces += rng.normal(scale=force_drift, size=(snapshots, 1, 3))
    if duplicate:
        displacements = np.concatenate([displacements, displacements[:5]], axis=0)
        forces = np.concatenate([forces, forces[:5]], axis=0)
    return {
        "name": name,
        "cell": structure,
        "displacements": displacements.tolist(),
        "forces": forces.tolist(),
        "arguments": {"is_symmetry": bool(is_symmetry), "symprec": 1e-5},
        "compare_tensor": bool(compare_tensor),
    }


def transformed_pair():
    base = generated("p1_transform_base", P1_THREE, 38, 6101)
    angle = 0.53
    rotation = np.array([
        [math.cos(angle), -math.sin(angle), 0.0],
        [math.sin(angle), math.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ])
    rotated = generated("placeholder", P1_THREE, 4, 1)
    rotated["name"] = "p1_transform_rotated"
    rotated["cell"] = {
        **P1_THREE,
        "cell": (np.asarray(P1_THREE["cell"]) @ rotation.T).tolist(),
    }
    rotated["displacements"] = (
        np.asarray(base["displacements"]) @ rotation.T
    ).tolist()
    rotated["forces"] = (np.asarray(base["forces"]) @ rotation.T).tolist()
    rotated["arguments"] = dict(base["arguments"])
    return base, rotated


def permutation_pair():
    base = generated("p1_permutation_base", P1_THREE, 39, 7103)
    order = np.array([2, 0, 1])
    swapped = {
        "name": "p1_permutation_swapped",
        "cell": {
            "symbols": [P1_THREE["symbols"][index] for index in order],
            "cell": P1_THREE["cell"],
            "scaled_positions": np.asarray(P1_THREE["scaled_positions"])[order].tolist(),
        },
        "displacements": np.asarray(base["displacements"])[:, order].tolist(),
        "forces": np.asarray(base["forces"])[:, order].tolist(),
        "arguments": dict(base["arguments"]),
        "compare_tensor": True,
    }
    return base, swapped


def symmetry_rescued_underdetermined():
    return generated(
        "symmetry_rescued_underdetermined",
        zincblende(),
        2,
        8107,
        is_symmetry=True,
    )


def hidden_cases():
    transform_base, transform_rotated = transformed_pair()
    permutation_base, permutation_swapped = permutation_pair()
    return [
        generated("p1_two_exact", P1_TWO, 24, 1001),
        generated("p1_three_exact", P1_THREE, 40, 1003),
        generated("p1_four_exact", P1_FOUR, 30, 1007),
        generated("p1_three_noisy", P1_THREE, 45, 2003, noise=2e-4),
        generated("p1_two_redundant", P1_TWO, 18, 2011, duplicate=True),
        generated("zincblende_projected", zincblende(), 10, 3001,
                  is_symmetry=True),
        generated("zincblende_noisy", zincblende(), 12, 3011,
                  is_symmetry=True, noise=3e-4),
        generated("zincblende_scaled", zincblende(), 11, 4001,
                  is_symmetry=True, amplitude=0.012),
        generated("wurtzite_projected", wurtzite(), 26, 4013,
                  is_symmetry=True),
        transform_base,
        transform_rotated,
        permutation_base,
        permutation_swapped,
        symmetry_rescued_underdetermined(),
        generated("p1_uniform_force_drift", P1_THREE, 42, 9001,
                  force_drift=4e-4),
    ]
