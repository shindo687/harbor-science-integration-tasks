#!/usr/bin/env python3
"""Root-only protocol adapter to the native AutoDock Vina potentials."""

from __future__ import annotations

import json
import math
import subprocess
import sys


REFERENCE = "/opt/reference-vina/vina-potential-reference"
TYPE_NAMES = (
    "C_H", "C_P", "N_P", "N_D", "N_A", "N_DA", "O_P", "O_D", "O_A",
    "O_DA", "S_P", "P_P", "F_H", "Cl_H", "Br_H", "I_H", "Si", "At",
    "Met_D",
)
TYPE_INDEX = {name: i for i, name in enumerate(TYPE_NAMES)}
TERM_NAMES = ("gauss1", "gauss2", "repulsion", "hydrophobic", "hydrogen")


def validate(case):
    if case.get("schema") != "structharbor-openmm-vina-score-v1":
        raise ValueError("unsupported schema")
    groups = []
    for key in ("receptor", "ligand"):
        group = case.get(key)
        if not isinstance(group, dict):
            raise ValueError(f"missing {key}")
        types = group.get("types")
        positions = group.get("positions")
        if not isinstance(types, list) or not isinstance(positions, list):
            raise ValueError("types and positions must be lists")
        if len(types) != len(positions) or len(types) > 256:
            raise ValueError("atom count mismatch or limit exceeded")
        checked = []
        for atom_type, xyz in zip(types, positions):
            if atom_type not in TYPE_INDEX:
                raise ValueError("unsupported XS atom type")
            if (not isinstance(xyz, list) or len(xyz) != 3
                    or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                           or not math.isfinite(v) for v in xyz)):
                raise ValueError("invalid coordinate")
            checked.append(tuple(float(v) for v in xyz))
        groups.append((types, checked))
    torsions = case.get("num_rotatable_bonds")
    cutoff = case.get("cutoff")
    if not isinstance(torsions, int) or isinstance(torsions, bool) or not 0 <= torsions <= 64:
        raise ValueError("num_rotatable_bonds must be an integer from 0 through 64")
    if (not isinstance(cutoff, (int, float)) or isinstance(cutoff, bool)
            or not math.isfinite(cutoff) or not 0 < cutoff <= 8.0):
        raise ValueError("cutoff must be finite and in (0, 8]")
    return groups[0], groups[1], torsions, float(cutoff)


def distance_vector(first, second):
    vector = tuple(second[k] - first[k] for k in range(3))
    distance = math.sqrt(sum(v*v for v in vector))
    return distance, vector


def run_one(case):
    receptor, ligand, torsions, cutoff = validate(case)
    pairs = []
    protocol = []
    for i, (first_type, first_xyz) in enumerate(zip(*receptor)):
        for j, (second_type, second_xyz) in enumerate(zip(*ligand)):
            distance, vector = distance_vector(first_xyz, second_xyz)
            if distance <= 1e-6:
                raise ValueError("coincident receptor and ligand atoms")
            if distance < cutoff:
                pairs.append((i, j, distance, vector, first_type, second_type))
                protocol.append(f"{TYPE_INDEX[first_type]} {TYPE_INDEX[second_type]} {distance:.17g}")
    request = f"{torsions} {len(protocol)}\n" + "\n".join(protocol) + "\n"
    completed = subprocess.run(
        [REFERENCE], input=request, text=True, capture_output=True,
        timeout=30, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"native Vina adapter failed ({completed.returncode})")
    lines = completed.stdout.splitlines()
    if len(lines) != len(pairs) + 1:
        raise RuntimeError("native Vina adapter row count mismatch")
    divisor = float(lines[0])
    terms = {name: 0.0 for name in TERM_NAMES}
    receptor_forces = [[0.0, 0.0, 0.0] for _ in receptor[0]]
    ligand_forces = [[0.0, 0.0, 0.0] for _ in ligand[0]]
    contributions = []
    for pair, line in zip(pairs, lines[1:]):
        i, j, distance, vector, first_type, second_type = pair
        values = [float(value) for value in line.split()]
        if len(values) != 10 or any(not math.isfinite(v) for v in values):
            raise RuntimeError("invalid native Vina adapter output")
        pair_terms = dict(zip(TERM_NAMES, values[:5]))
        pair_total = sum(pair_terms.values())
        contributions.append({
            "receptor_index": i, "ligand_index": j,
            "receptor_type": first_type, "ligand_type": second_type,
            "distance": distance, "terms": pair_terms, "raw_total": pair_total,
        })
        for name, value in pair_terms.items():
            terms[name] += value
        radial = sum(values[5:]) / divisor
        unit = [component / distance for component in vector]
        ligand_force = [-radial * component for component in unit]
        for axis in range(3):
            ligand_forces[j][axis] += ligand_force[axis]
            receptor_forces[i][axis] -= ligand_force[axis]
    raw = sum(terms.values())
    affinity = raw / divisor
    return {
        "affinity": affinity,
        "raw_interaction": raw,
        "torsional_penalty": affinity - raw,
        "torsional_divisor": divisor,
        "terms": terms,
        "pairs": contributions,
        "receptor_forces": receptor_forces,
        "ligand_forces": ligand_forces,
    }


def main():
    request = json.load(sys.stdin)
    response = []
    for case in request["cases"]:
        try:
            response.append({"name": case.get("name"), "result": run_one(case)})
        except Exception as exc:
            response.append({"name": case.get("name"), "error": type(exc).__name__})
    json.dump({"cases": response}, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()

