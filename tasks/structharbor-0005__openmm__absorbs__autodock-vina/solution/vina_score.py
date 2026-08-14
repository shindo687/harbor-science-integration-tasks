"""Vina-compatible scoring for fixed, pretyped receptor/ligand poses.

The bounded interface in this module intentionally starts after atom typing and
does not perform docking.  Coordinates are in angstrom, energies are in
kcal/mol, and returned coordinate forces are in kcal/mol/angstrom.
"""

from __future__ import annotations

import math


_TYPE_NAMES = (
    "C_H", "C_P", "N_P", "N_D", "N_A", "N_DA", "O_P", "O_D", "O_A",
    "O_DA", "S_P", "P_P", "F_H", "Cl_H", "Br_H", "I_H", "Si", "At",
    "Met_D",
)
_RADII = dict(zip(_TYPE_NAMES, (
    1.9, 1.9, 1.8, 1.8, 1.8, 1.8, 1.7, 1.7, 1.7, 1.7,
    2.0, 2.1, 1.5, 1.8, 2.0, 2.2, 2.2, 2.3, 1.2,
)))
_HYDROPHOBIC = frozenset(("C_H", "F_H", "Cl_H", "Br_H", "I_H"))
_ACCEPTORS = frozenset(("N_A", "N_DA", "O_A", "O_DA"))
_DONORS = frozenset(("N_D", "N_DA", "O_D", "O_DA", "Met_D"))
_TERMS = ("gauss1", "gauss2", "repulsion", "hydrophobic", "hydrogen")

_GAUSS1_WEIGHT = -0.035579
_GAUSS2_WEIGHT = -0.005156
_REPULSION_WEIGHT = 0.840245
_HYDROPHOBIC_WEIGHT = -0.035069
_HYDROGEN_WEIGHT = -0.587439
_ROTATABLE_WEIGHT = 0.05846


def _validate_group(types, positions, label):
    if not isinstance(types, list) or not isinstance(positions, list):
        raise TypeError(f"{label} types and positions must be lists")
    if len(types) != len(positions) or len(types) > 256:
        raise ValueError(f"{label} atom count mismatch or limit exceeded")
    checked_positions = []
    for atom_type, xyz in zip(types, positions):
        if atom_type not in _RADII:
            raise ValueError(f"unsupported Vina XS atom type: {atom_type!r}")
        if not isinstance(xyz, list) or len(xyz) != 3:
            raise ValueError(f"invalid {label} coordinate")
        checked = []
        for component in xyz:
            if (not isinstance(component, (int, float))
                    or isinstance(component, bool)
                    or not math.isfinite(component)):
                raise ValueError(f"invalid {label} coordinate")
            checked.append(float(component))
        checked_positions.append(tuple(checked))
    return list(types), checked_positions


def _slope(value, good, bad):
    if value <= good:
        return 1.0
    if value >= bad:
        return 0.0
    return (bad - value) / (bad - good)


def _weighted_values(first_type, second_type, distance):
    if distance >= 8.0:
        return {name: 0.0 for name in _TERMS}
    surface_distance = distance - _RADII[first_type] - _RADII[second_type]

    gauss1_raw = math.exp(-((surface_distance / 0.5) ** 2))
    gauss2_argument = (surface_distance - 3.0) / 2.0
    gauss2_raw = math.exp(-(gauss2_argument ** 2))
    repulsion_raw = surface_distance * surface_distance if surface_distance <= 0 else 0.0

    hydrophobic_pair = first_type in _HYDROPHOBIC and second_type in _HYDROPHOBIC
    hydrophobic_raw = _slope(surface_distance, 0.5, 1.5) if hydrophobic_pair else 0.0
    hydrogen_pair = ((first_type in _DONORS and second_type in _ACCEPTORS)
                     or (second_type in _DONORS and first_type in _ACCEPTORS))
    hydrogen_raw = _slope(surface_distance, -0.7, 0.0) if hydrogen_pair else 0.0

    return {
        "gauss1": _GAUSS1_WEIGHT * gauss1_raw,
        "gauss2": _GAUSS2_WEIGHT * gauss2_raw,
        "repulsion": _REPULSION_WEIGHT * repulsion_raw,
        "hydrophobic": _HYDROPHOBIC_WEIGHT * hydrophobic_raw,
        "hydrogen": _HYDROGEN_WEIGHT * hydrogen_raw,
    }


def _pair_terms(first_type, second_type, distance):
    values = _weighted_values(first_type, second_type, distance)
    # Use Vina's symmetric force convention.  Besides matching the native
    # implementation at piecewise-linear kinks, this keeps value and force
    # definitions coupled in one small, auditable routine.
    step = 1e-6
    high = _weighted_values(first_type, second_type, distance + step)
    low = _weighted_values(first_type, second_type, distance - step)
    derivatives = {
        name: (high[name] - low[name]) / (2.0 * step) for name in _TERMS
    }
    return values, derivatives


def score_vina_pose(receptor_types, receptor_positions, ligand_types,
                    ligand_positions, num_rotatable_bonds, cutoff=8.0):
    """Score one fixed pose using the default AutoDock Vina potential.

    The result contains the normalized affinity, all five weighted raw terms,
    per-pair contributions, and forces for both atom groups.  Only cross-group
    atom pairs whose distance is strictly below ``cutoff`` are included.
    """
    receptor_types, receptor_positions = _validate_group(
        receptor_types, receptor_positions, "receptor")
    ligand_types, ligand_positions = _validate_group(
        ligand_types, ligand_positions, "ligand")
    if (not isinstance(num_rotatable_bonds, int)
            or isinstance(num_rotatable_bonds, bool)
            or not 0 <= num_rotatable_bonds <= 64):
        raise ValueError("num_rotatable_bonds must be an integer from 0 through 64")
    if (not isinstance(cutoff, (int, float)) or isinstance(cutoff, bool)
            or not math.isfinite(cutoff) or not 0 < cutoff <= 8.0):
        raise ValueError("cutoff must be finite and in (0, 8]")
    cutoff = float(cutoff)

    divisor = 1.0 + _ROTATABLE_WEIGHT * num_rotatable_bonds / 5.0
    terms = {name: 0.0 for name in _TERMS}
    receptor_forces = [[0.0, 0.0, 0.0] for _ in receptor_types]
    ligand_forces = [[0.0, 0.0, 0.0] for _ in ligand_types]
    pairs = []

    for receptor_index, (first_type, first_xyz) in enumerate(
            zip(receptor_types, receptor_positions)):
        for ligand_index, (second_type, second_xyz) in enumerate(
                zip(ligand_types, ligand_positions)):
            vector = tuple(second_xyz[axis] - first_xyz[axis] for axis in range(3))
            distance = math.sqrt(sum(component * component for component in vector))
            if distance <= 1e-6:
                raise ValueError("coincident receptor and ligand atoms")
            if distance >= cutoff:
                continue

            pair_terms, derivatives = _pair_terms(first_type, second_type, distance)
            pair_total = sum(pair_terms.values())
            pairs.append({
                "receptor_index": receptor_index,
                "ligand_index": ligand_index,
                "receptor_type": first_type,
                "ligand_type": second_type,
                "distance": distance,
                "terms": pair_terms,
                "raw_total": pair_total,
            })
            for name in _TERMS:
                terms[name] += pair_terms[name]

            radial_derivative = sum(derivatives.values()) / divisor
            for axis in range(3):
                ligand_force = -radial_derivative * vector[axis] / distance
                ligand_forces[ligand_index][axis] += ligand_force
                receptor_forces[receptor_index][axis] -= ligand_force

    raw_interaction = sum(terms.values())
    affinity = raw_interaction / divisor
    return {
        "affinity": affinity,
        "raw_interaction": raw_interaction,
        "torsional_penalty": affinity - raw_interaction,
        "torsional_divisor": divisor,
        "terms": terms,
        "pairs": pairs,
        "receptor_forces": receptor_forces,
        "ligand_forces": ligand_forces,
    }
