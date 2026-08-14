#!/usr/bin/env python3
"""Deterministic typed-pose fixtures for STRUCTHARBOR-0005."""

from __future__ import annotations

import copy
import math


def case(name, receptor_types, receptor_positions, ligand_types,
         ligand_positions, torsions=0, cutoff=8.0):
    return {
        "name": name,
        "schema": "structharbor-openmm-vina-score-v1",
        "receptor": {"types": list(receptor_types),
                     "positions": copy.deepcopy(receptor_positions)},
        "ligand": {"types": list(ligand_types),
                   "positions": copy.deepcopy(ligand_positions)},
        "num_rotatable_bonds": torsions,
        "cutoff": cutoff,
    }


def _rotation(axis, degrees):
    x, y, z = axis
    norm = math.sqrt(x*x + y*y + z*z)
    x, y, z = x/norm, y/norm, z/norm
    c = math.cos(math.radians(degrees))
    s = math.sin(math.radians(degrees))
    t = 1-c
    return (
        (t*x*x+c, t*x*y-s*z, t*x*z+s*y),
        (t*x*y+s*z, t*y*y+c, t*y*z-s*x),
        (t*x*z-s*y, t*y*z+s*x, t*z*z+c),
    )


def transform(value, axis=(1, 2, 3), degrees=67, shift=(12, -8, 5)):
    result = copy.deepcopy(value)
    matrix = _rotation(axis, degrees)
    for group in ("receptor", "ligand"):
        positions = []
        for xyz in result[group]["positions"]:
            positions.append([
                sum(matrix[row][column] * xyz[column] for column in range(3))
                + shift[row]
                for row in range(3)
            ])
        result[group]["positions"] = positions
    return result


def _mixed(name="mixed", torsions=5):
    return case(
        name,
        ["C_H", "O_A", "N_D", "Cl_H"],
        [[0, 0, 0], [4.6, 0.2, 0], [0.3, 5.0, 0], [4.8, 5.2, 0.2]],
        ["C_H", "N_D", "O_A", "F_H"],
        [[3.75, 0.1, 0], [4.5, 3.35, 0.1], [0.2, 1.55, 3.0], [3.2, 4.8, 2.5]],
        torsions,
    )


def public_cases():
    return [
        case("public_hydrophobic_contact", ["C_H"], [[0, 0, 0]],
             ["C_H"], [[3.8, 0, 0]], 0),
        case("public_hydrogen_bond", ["O_A"], [[0, 0, 0]],
             ["N_D"], [[3.1, 0, 0]], 3),
        case("public_steric_clash", ["C_H"], [[0, 0, 0]],
             ["C_P"], [[2.35, 0, 0]], 1),
        _mixed("public_mixed_pose", 5),
        case("public_cutoff_boundary", ["C_H"], [[0, 0, 0]],
             ["C_H", "C_H", "N_P"],
             [[7.999, 0, 0], [8.0, 0, 0], [8.001, 0, 0]], 0),
    ]


def hidden_cases():
    mixed = _mixed("hidden_mixed_torsion_two", 2)
    rotated = transform(mixed, axis=(-2, 1, 4), degrees=113,
                        shift=(-17, 31, 9))
    rotated["name"] = "hidden_mixed_rigid_transform"
    swapped = case(
        "hidden_group_swap",
        mixed["ligand"]["types"], mixed["ligand"]["positions"],
        mixed["receptor"]["types"], mixed["receptor"]["positions"], 2,
    )
    return [
        case("hidden_gauss2_polar", ["C_P"], [[0, 0, 0]],
             ["N_P"], [[6.7, 0, 0]], 0),
        case("hidden_fluorine_hydrophobic", ["F_H"], [[0, 0, 0]],
             ["C_H"], [[4.0, 0, 0]], 1),
        case("hidden_chlorine_hydrophobic", ["Cl_H"], [[0, 0, 0]],
             ["Br_H"], [[4.55, 0, 0]], 4),
        case("hidden_hbond_good_boundary", ["N_D"], [[0, 0, 0]],
             ["O_A"], [[2.8, 0, 0]], 0),
        case("hidden_hbond_bad_boundary", ["O_D"], [[0, 0, 0]],
             ["N_A"], [[3.5, 0, 0]], 7),
        case("hidden_metal_donor", ["Met_D"], [[0, 0, 0]],
             ["O_A"], [[2.55, 0.1, 0]], 2),
        _mixed("hidden_mixed_zero_torsion", 0),
        mixed,
        rotated,
        case("hidden_custom_cutoff", ["C_H", "O_A"], [[0, 0, 0], [0, 4, 0]],
             ["C_H", "N_D"], [[4.499, 0, 0], [4.5, 4, 0]], 3, 4.5),
        case("hidden_no_interaction", ["C_H", "O_A"], [[0, 0, 0], [0, 3, 0]],
             ["C_H", "N_D"], [[25, 0, 0], [25, 3, 0]], 9),
        case("hidden_dense_pose",
             ["C_H", "C_P", "N_A", "O_D"],
             [[0, 0, 0], [0, 4, 0], [4, 0, 0], [4, 4, 0]],
             ["F_H", "N_DA", "O_A", "S_P"],
             [[2, 2, 1], [1, 1, 4], [5, 2, 2], [2, 5, 3]], 6),
        swapped,
        case("hidden_high_torsion", ["I_H", "C_H"], [[0, 0, 0], [0, 5, 0]],
             ["C_H", "O_A"], [[4.5, 0, 0], [0, 2, 0]], 20),
        case("hidden_near_native_cutoff", ["P_P", "C_H"],
             [[0, 0, 0], [0, 2, 0]], ["S_P", "C_P"],
             [[7.998, 0, 0], [7.999, 2, 0]], 0),
    ]
