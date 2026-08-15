"""Bounded, clean-room protein interface energy decomposition.

This module intentionally depends only on the Python standard library.  It is
an independent educational potential and is not a Ref2015 implementation.
"""

from __future__ import annotations

import math


TERM_NAMES = ("lj_repulsive", "lj_attractive", "coulomb", "hbond", "sasa")
PARAMETER_NAMES = {
    "cutoff", "switch_distance", "dielectric", "probe_radius",
    "solvation_gamma", "hbond_strength", "hbond_distance", "hbond_width",
}
ATOM_NAMES = {
    "id", "chain", "residue", "coord", "sigma", "epsilon", "charge",
    "sasa_radius", "donor_direction", "acceptor_direction",
}


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _vector(value, field, *, allow_none=False):
    if value is None and allow_none:
        return None
    if not isinstance(value, list) or len(value) != 3 or not all(_number(x) for x in value):
        raise ValueError(f"{field} must be a finite length-three list")
    return tuple(float(x) for x in value)


def _unit(value, field):
    vector = _vector(value, field)
    norm = math.sqrt(sum(x * x for x in vector))
    if norm <= 1.0e-12:
        raise ValueError(f"{field} must be nonzero")
    return tuple(x / norm for x in vector)


def _positive(value, field, upper):
    if not _number(value) or not 0.0 < float(value) <= upper:
        raise ValueError(f"{field} is outside the supported range")
    return float(value)


def _validate(packet):
    expected = {
        "name", "atoms", "group_a", "group_b", "separation_distance",
        "separation_direction", "parameters", "compute_forces",
    }
    if not isinstance(packet, dict) or set(packet) != expected:
        raise ValueError("packet fields differ from the interface_energy_lite schema")
    name = packet["name"]
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
    if not isinstance(name, str) or not name or len(name) > 80 or any(c not in allowed for c in name):
        raise ValueError("invalid packet name")
    atoms = packet["atoms"]
    if not isinstance(atoms, list) or not 2 <= len(atoms) <= 160:
        raise ValueError("atoms must contain between 2 and 160 entries")
    if not isinstance(packet["compute_forces"], bool):
        raise ValueError("compute_forces must be boolean")
    if packet["compute_forces"] and len(atoms) > 24:
        raise ValueError("force evaluation is bounded to 24 atoms")

    identifiers = set()
    normalized = []
    for index, atom in enumerate(atoms):
        if not isinstance(atom, dict) or set(atom) != ATOM_NAMES:
            raise ValueError(f"atom {index} fields differ from the schema")
        identifier = atom["id"]
        chain = atom["chain"]
        residue = atom["residue"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("atom ids must be unique nonempty strings")
        identifiers.add(identifier)
        if not isinstance(chain, str) or not chain or len(chain) > 8:
            raise ValueError("invalid chain id")
        if not isinstance(residue, str) or not residue or len(residue) > 32:
            raise ValueError("invalid residue id")
        coord = _vector(atom["coord"], f"atom {index} coord")
        if any(abs(x) > 10000.0 for x in coord):
            raise ValueError("coordinate magnitude exceeds the bounded contract")
        donor = atom["donor_direction"]
        acceptor = atom["acceptor_direction"]
        normalized.append({
            "id": identifier,
            "chain": chain,
            "residue_key": f"{chain}:{residue}",
            "coord": coord,
            "sigma": _positive(atom["sigma"], "sigma", 20.0),
            "epsilon": _positive(atom["epsilon"], "epsilon", 100.0),
            "charge": float(atom["charge"]) if _number(atom["charge"]) else None,
            "sasa_radius": _positive(atom["sasa_radius"], "sasa_radius", 10.0),
            "donor": None if donor is None else _unit(donor, "donor_direction"),
            "acceptor": None if acceptor is None else _unit(acceptor, "acceptor_direction"),
        })
        if normalized[-1]["charge"] is None or abs(normalized[-1]["charge"]) > 10.0:
            raise ValueError("charge is outside the supported range")

    chains = {atom["chain"] for atom in normalized}
    groups = []
    for field in ("group_a", "group_b"):
        group = packet[field]
        if (not isinstance(group, list) or not group
                or any(not isinstance(chain, str) or not chain for chain in group)
                or len(set(group)) != len(group)):
            raise ValueError(f"{field} must be a nonempty unique chain list")
        groups.append(set(group))
    if groups[0] & groups[1] or groups[0] | groups[1] != chains:
        raise ValueError("chain groups must be disjoint and cover every atom chain")
    distance = packet["separation_distance"]
    if not _number(distance) or not 0.0 < float(distance) <= 200.0:
        raise ValueError("invalid separation distance")
    direction = _unit(packet["separation_direction"], "separation_direction")

    supplied = packet["parameters"]
    if not isinstance(supplied, dict) or set(supplied) != PARAMETER_NAMES:
        raise ValueError("parameter fields differ from the schema")
    parameters = {
        "cutoff": _positive(supplied["cutoff"], "cutoff", 50.0),
        "switch_distance": _positive(supplied["switch_distance"], "switch_distance", 50.0),
        "dielectric": _positive(supplied["dielectric"], "dielectric", 1000.0),
        "probe_radius": _positive(supplied["probe_radius"], "probe_radius", 10.0),
        "solvation_gamma": _positive(supplied["solvation_gamma"], "solvation_gamma", 10.0),
        "hbond_strength": _positive(supplied["hbond_strength"], "hbond_strength", 100.0),
        "hbond_distance": _positive(supplied["hbond_distance"], "hbond_distance", 10.0),
        "hbond_width": _positive(supplied["hbond_width"], "hbond_width", 10.0),
    }
    if parameters["switch_distance"] >= parameters["cutoff"]:
        raise ValueError("switch_distance must be smaller than cutoff")
    return normalized, groups[1], float(distance), direction, parameters


def _switch(distance, parameters):
    start = parameters["switch_distance"]
    cutoff = parameters["cutoff"]
    if distance <= start:
        return 1.0
    if distance >= cutoff:
        return 0.0
    fraction = (distance - start) / (cutoff - start)
    return 1.0 - 3.0 * fraction * fraction + 2.0 * fraction * fraction * fraction


def _oriented_hbond(donor, acceptor, unit_delta, distance, scale, parameters):
    if donor is None or acceptor is None:
        return 0.0
    donor_cosine = max(0.0, sum(donor[k] * unit_delta[k] for k in range(3)))
    acceptor_cosine = max(0.0, -sum(acceptor[k] * unit_delta[k] for k in range(3)))
    offset = (distance - parameters["hbond_distance"]) / parameters["hbond_width"]
    radial = math.exp(-0.5 * offset * offset)
    return (-parameters["hbond_strength"] * radial * donor_cosine ** 2
            * acceptor_cosine ** 2 * scale)


def _state(atoms, coordinates, parameters):
    totals = {name: 0.0 for name in TERM_NAMES}
    residues = sorted({atom["residue_key"] for atom in atoms})
    contributions = {key: {name: 0.0 for name in TERM_NAMES} for key in residues}
    occlusion = [0.0] * len(atoms)
    for i in range(len(atoms)):
        for j in range(i + 1, len(atoms)):
            delta = tuple(coordinates[j][k] - coordinates[i][k] for k in range(3))
            distance2 = sum(value * value for value in delta)
            if distance2 <= 1.0e-16:
                raise ValueError("coincident atoms are not supported")
            distance = math.sqrt(distance2)
            unit_delta = tuple(value / distance for value in delta)
            scale = _switch(distance, parameters)
            sigma = 0.5 * (atoms[i]["sigma"] + atoms[j]["sigma"])
            epsilon = math.sqrt(atoms[i]["epsilon"] * atoms[j]["epsilon"])
            ratio = sigma / distance
            pair = {
                "lj_repulsive": 4.0 * epsilon * ratio ** 12 * scale,
                "lj_attractive": -4.0 * epsilon * ratio ** 6 * scale,
                "coulomb": (332.06371 * atoms[i]["charge"] * atoms[j]["charge"]
                            / (parameters["dielectric"] * distance) * scale),
                "hbond": (
                    _oriented_hbond(atoms[i]["donor"], atoms[j]["acceptor"],
                                    unit_delta, distance, scale, parameters)
                    + _oriented_hbond(atoms[j]["donor"], atoms[i]["acceptor"],
                                      tuple(-value for value in unit_delta), distance,
                                      scale, parameters)
                ),
            }
            for term, value in pair.items():
                totals[term] += value
                contributions[atoms[i]["residue_key"]][term] += 0.5 * value
                contributions[atoms[j]["residue_key"]][term] += 0.5 * value
            reach = (atoms[i]["sasa_radius"] + atoms[j]["sasa_radius"]
                     + 2.0 * parameters["probe_radius"])
            overlap = math.exp(-((distance / reach) ** 6))
            occlusion[i] += overlap
            occlusion[j] += overlap
    for index, atom in enumerate(atoms):
        expanded = atom["sasa_radius"] + parameters["probe_radius"]
        energy = (parameters["solvation_gamma"] * 4.0 * math.pi * expanded ** 2
                  * math.exp(-occlusion[index]))
        totals["sasa"] += energy
        contributions[atom["residue_key"]]["sasa"] += energy
    return totals, contributions


def _evaluate(atoms, coordinates, moving_group, distance, direction, parameters):
    unbound = []
    for atom, coord in zip(atoms, coordinates):
        if atom["chain"] in moving_group:
            unbound.append(tuple(coord[k] + distance * direction[k] for k in range(3)))
        else:
            unbound.append(coord)
    bound_terms, bound_residues = _state(atoms, coordinates, parameters)
    unbound_terms, unbound_residues = _state(atoms, unbound, parameters)
    delta_terms = {name: bound_terms[name] - unbound_terms[name] for name in TERM_NAMES}
    return bound_terms, unbound_terms, delta_terms, bound_residues, unbound_residues


def score_interface(packet):
    """Validate and score one interface-energy-lite packet."""
    atoms, moving_group, distance, direction, parameters = _validate(packet)
    coordinates = [atom["coord"] for atom in atoms]
    bound, unbound, delta, bound_residues, unbound_residues = _evaluate(
        atoms, coordinates, moving_group, distance, direction, parameters
    )
    per_residue = []
    for key in sorted(bound_residues):
        terms = {name: bound_residues[key][name] - unbound_residues[key][name]
                 for name in TERM_NAMES}
        per_residue.append({"residue": key, "terms": terms, "total": sum(terms.values())})

    forces = None
    if packet["compute_forces"]:
        step = 1.0e-5
        forces = []
        for atom_index in range(len(atoms)):
            row = []
            for axis in range(3):
                plus = list(coordinates)
                minus = list(coordinates)
                plus_coord = list(coordinates[atom_index])
                minus_coord = list(coordinates[atom_index])
                plus_coord[axis] += step
                minus_coord[axis] -= step
                plus[atom_index] = tuple(plus_coord)
                minus[atom_index] = tuple(minus_coord)
                plus_delta = _evaluate(atoms, plus, moving_group, distance,
                                       direction, parameters)[2]
                minus_delta = _evaluate(atoms, minus, moving_group, distance,
                                        direction, parameters)[2]
                row.append(-(sum(plus_delta.values()) - sum(minus_delta.values()))
                           / (2.0 * step))
            forces.append(row)
    return {
        "bound": {"terms": bound, "total": sum(bound.values())},
        "unbound": {"terms": unbound, "total": sum(unbound.values())},
        "delta": {"terms": delta, "total": sum(delta.values())},
        "per_residue": per_residue,
        "forces": forces,
    }
