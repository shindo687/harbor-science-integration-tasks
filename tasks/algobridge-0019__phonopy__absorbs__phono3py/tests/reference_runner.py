#!/usr/bin/env python3
"""Locked phonopy-to-phono3py FC3 reference runner."""

from __future__ import annotations

import json
import sys

import numpy as np
from phonopy.structure.atoms import PhonopyAtoms
from phono3py import Phono3py

from model import constrained_design, design_diagnostics, predict_forces


def jsonify(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {key: jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonify(item) for item in value]
    return value


def make_cell(specification):
    return PhonopyAtoms(
        symbols=specification["symbols"],
        cell=specification["cell"],
        scaled_positions=specification["scaled_positions"],
    )


def run_one(item):
    supercell = make_cell(item["cell"])
    displacements = np.asarray(item["displacements"], dtype=float)
    forces = np.asarray(item["forces"], dtype=float)
    arguments = item["arguments"]
    workflow = Phono3py(
        supercell,
        supercell_matrix=np.eye(3, dtype=int),
        primitive_matrix=np.eye(3),
        is_symmetry=arguments["is_symmetry"],
        symprec=arguments["symprec"],
        log_level=0,
    )
    workflow.dataset = {
        "displacements": displacements,
        "forces": forces,
    }
    workflow.produce_fc3(fc_calculator="symfc", is_compact_fc=False)
    if workflow.fc2 is None or workflow.fc3 is None:
        raise RuntimeError("locked phono3py did not produce FC2/FC3")
    predicted = predict_forces(displacements, workflow.fc2, workflow.fc3)
    design, _, operation_count = constrained_design(
        supercell,
        displacements,
        forces,
        arguments["is_symmetry"],
        arguments["symprec"],
    )
    rank, singular_values, condition = design_diagnostics(design)
    return {
        "fc2": workflow.fc2,
        "fc3": workflow.fc3,
        "predicted_forces": predicted,
        "residual_norm": float(np.linalg.norm(predicted - forces)),
        "rank": rank,
        "singular_values": singular_values,
        "condition_number": condition,
        "n_parameters": int(design.shape[1]),
        "symmetry_operation_count": operation_count,
    }


def main():
    payload = json.load(sys.stdin)
    output = []
    for item in payload["cases"]:
        try:
            output.append({"name": item["name"], "result": jsonify(run_one(item))})
        except Exception as exc:  # reference failures are surfaced to the grader
            output.append({
                "name": item["name"],
                "error": type(exc).__name__,
                "message": str(exc),
            })
    json.dump({"cases": output}, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
