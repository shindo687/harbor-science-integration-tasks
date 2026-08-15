#!/usr/bin/env python3
"""Deterministic analytic fixtures for STRUCTHARBOR-0006."""

from __future__ import annotations

import copy
import math
import random


PARAMETERS = {
    "cutoff": 10.0,
    "switch_distance": 8.0,
    "dielectric": 40.0,
    "probe_radius": 1.4,
    "solvation_gamma": 0.005,
    "hbond_strength": 1.5,
    "hbond_distance": 2.9,
    "hbond_width": 0.45,
}


def atom(identifier, chain, residue, coord, *, sigma=3.4, epsilon=0.1,
         charge=0.0, radius=1.7, donor=None, acceptor=None):
    return {
        "id": identifier,
        "chain": chain,
        "residue": residue,
        "coord": [float(value) for value in coord],
        "sigma": float(sigma),
        "epsilon": float(epsilon),
        "charge": float(charge),
        "sasa_radius": float(radius),
        "donor_direction": donor,
        "acceptor_direction": acceptor,
    }


def packet(name, atoms, *, distance=30.0, direction=(1.0, 0.0, 0.0),
           forces=False, parameters=None):
    return {
        "name": name,
        "atoms": atoms,
        "group_a": ["A"],
        "group_b": ["B"],
        "separation_distance": float(distance),
        "separation_direction": [float(value) for value in direction],
        "parameters": copy.deepcopy(PARAMETERS if parameters is None else parameters),
        "compute_forces": bool(forces),
    }


PUBLIC_CASES = [
    packet("hydrophobic_pair", [
        atom("a1", "A", "LEU1", (0.0, -1.2, 0.0)),
        atom("a2", "A", "LEU1", (0.1, 1.3, 0.2)),
        atom("b1", "B", "VAL7", (4.0, -1.0, 0.1)),
        atom("b2", "B", "VAL7", (4.2, 1.4, -0.1)),
    ], forces=True),
    packet("salt_bridge", [
        atom("lys_nz", "A", "LYS4", (0.0, 0.0, 0.0), sigma=3.25,
             epsilon=0.08, charge=1.0, radius=1.55),
        atom("lys_cb", "A", "LYS4", (-1.7, 0.5, 0.0)),
        atom("asp_od", "B", "ASP9", (3.2, 0.0, 0.0), sigma=3.0,
             epsilon=0.12, charge=-1.0, radius=1.52),
        atom("asp_cg", "B", "ASP9", (4.7, 0.4, 0.0)),
    ], forces=True),
    packet("single_backbone_hbond", [
        atom("donor_n", "A", "ASN2", (0.0, 0.0, 0.0), sigma=2.6,
             epsilon=0.06, radius=1.55, donor=[1.0, 0.0, 0.0]),
        atom("acceptor_o", "B", "GLY8", (2.9, 0.0, 0.0), sigma=2.5,
             epsilon=0.08, radius=1.52, acceptor=[-1.0, 0.0, 0.0]),
    ], forces=True),
    packet("steric_clash", [
        atom("ca", "A", "ALA1", (0.0, 0.0, 0.0), sigma=3.8, epsilon=0.2),
        atom("cb", "B", "TRP5", (2.1, 0.0, 0.0), sigma=4.0, epsilon=0.25),
    ]),
    packet("mixed_interface", [
        atom("a_n", "A", "SER3", (0.0, 0.0, 0.0), sigma=2.8, epsilon=0.08,
             charge=0.3, radius=1.55, donor=[1.0, 0.0, 0.0]),
        atom("a_c1", "A", "SER3", (-0.4, 2.8, 0.2)),
        atom("a_c2", "A", "PHE4", (0.2, -2.7, -0.3), sigma=3.8, epsilon=0.18),
        atom("b_o", "B", "GLU8", (3.0, 0.1, 0.0), sigma=2.7, epsilon=0.12,
             charge=-0.5, radius=1.52, acceptor=[-1.0, 0.0, 0.0]),
        atom("b_c1", "B", "LEU9", (4.0, 2.7, 0.1), sigma=3.7, epsilon=0.15),
        atom("b_c2", "B", "LEU9", (4.1, -2.6, -0.2), sigma=3.7, epsilon=0.15),
    ], distance=35.0, forces=True),
]


def _random_case(index):
    rng = random.Random(6100 + index)
    count = 3 + index % 4
    atoms = []
    for group, chain, base_x in ((0, "A", 0.0), (1, "B", 3.1 + 0.18 * index)):
        for item in range(count):
            y = (item - 0.5 * (count - 1)) * 2.15 + rng.uniform(-0.22, 0.22)
            z = rng.uniform(-0.65, 0.65)
            x = base_x + rng.uniform(-0.28, 0.28)
            charge = (1.0 if (item + index) % 5 == 0 else
                      -0.7 if (item + 2 * index) % 6 == 0 else 0.0)
            donor = [1.0, 0.0, 0.0] if group == 0 and item == 0 and index % 2 == 0 else None
            acceptor = [-1.0, 0.0, 0.0] if group == 1 and item == 0 and index % 2 == 0 else None
            atoms.append(atom(
                f"{chain.lower()}{item}", chain, f"R{index}_{item}", (x, y, z),
                sigma=2.8 + 0.18 * ((item + index) % 6),
                epsilon=0.06 + 0.025 * ((2 * item + index) % 5),
                charge=charge, radius=1.45 + 0.08 * ((item + index) % 5),
                donor=donor, acceptor=acceptor,
            ))
    parameters = copy.deepcopy(PARAMETERS)
    parameters["dielectric"] = 24.0 + 7.0 * (index % 6)
    parameters["solvation_gamma"] = 0.003 + 0.0007 * (index % 5)
    parameters["hbond_strength"] = 1.1 + 0.17 * (index % 7)
    parameters["hbond_distance"] = 2.75 + 0.05 * (index % 5)
    return packet(
        f"hidden_mixed_{index:02d}", atoms,
        distance=18.0 + index,
        direction=(1.0, 0.13 * ((index % 3) - 1), 0.09 * ((index % 4) - 1.5)),
        forces=index < 6,
        parameters=parameters,
    )


def public_cases():
    return copy.deepcopy(PUBLIC_CASES)


def hidden_cases():
    return [_random_case(index) for index in range(18)]


def rotated_translated(source):
    result = copy.deepcopy(source)
    result["name"] += "_rigid_transform"

    def transform(vector, translate=False):
        x, y, z = vector
        rotated = [-y, x, z]
        if translate:
            return [rotated[0] + 7.5, rotated[1] - 4.0, rotated[2] + 2.25]
        return rotated

    for item in result["atoms"]:
        item["coord"] = transform(item["coord"], True)
        if item["donor_direction"] is not None:
            item["donor_direction"] = transform(item["donor_direction"])
        if item["acceptor_direction"] is not None:
            item["acceptor_direction"] = transform(item["acceptor_direction"])
    result["separation_direction"] = transform(result["separation_direction"])
    return result


def swapped_groups(source):
    result = copy.deepcopy(source)
    result["name"] += "_group_swap"
    result["group_a"], result["group_b"] = result["group_b"], result["group_a"]
    result["separation_direction"] = [-value for value in result["separation_direction"]]
    return result


def separation_scan(source):
    result = []
    for distance in (20.0, 40.0, 80.0, 160.0):
        item = copy.deepcopy(source)
        item["name"] += f"_separation_{int(distance)}"
        item["separation_distance"] = distance
        item["compute_forces"] = False
        result.append(item)
    return result


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
