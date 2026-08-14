#!/usr/bin/env python3
"""Locked AlphaFold parser to locked ProDy reference pipeline."""

from __future__ import annotations

import json
import sys
import warnings

import numpy as np
from alphafold.common import protein as af_protein
from alphafold.common import residue_constants
from prody import ANM, GNM, calcCrossCorr, calcSqFlucts


CA_INDEX = residue_constants.atom_order["CA"]


def parse_structure(case):
    if case["format"] == "pdb":
        return af_protein.from_pdb_string(case["structure"])
    if case["format"] == "mmcif":
        return af_protein.from_mmcif_string(case["structure"])
    raise ValueError("unsupported structure format")


def normalize_chains(value):
    if value is None:
        return None
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return np.asarray([int(value)], dtype=int)
    return np.asarray(list(value), dtype=int)


def select(protein, arguments):
    mask = protein.atom_mask[:, CA_INDEX] >= 0.5
    chains = normalize_chains(arguments.get("chain_indices"))
    if chains is not None:
        mask &= np.isin(protein.chain_index, chains)
    threshold = arguments.get("plddt_threshold")
    if threshold is not None:
        mask &= protein.b_factors[:, CA_INDEX] >= float(threshold)
    indices = np.flatnonzero(mask)
    coords = np.asarray(protein.atom_positions[indices, CA_INDEX], dtype=float)
    mapping = [
        {
            "source_index": int(index),
            "chain_index": int(protein.chain_index[index]),
            "residue_index": int(protein.residue_index[index]),
            "aatype": int(protein.aatype[index]),
        }
        for index in indices
    ]
    return coords, mapping


def run_one(case):
    arguments = case["arguments"]
    structure = parse_structure(case)
    coords, mapping = select(structure, arguments)
    model_name = str(arguments.get("model", "gnm")).lower()
    cutoff = float(arguments.get("cutoff", 10.0))
    gamma = float(arguments.get("gamma", 1.0))
    n_modes = int(arguments.get("n_modes", 5))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        if model_name == "gnm":
            model = GNM(case["name"])
            model.buildKirchhoff(
                coords, cutoff=cutoff, gamma=gamma, kdtree=False
            )
            network = np.asarray(model.getKirchhoff(), dtype=float)
        elif model_name == "anm":
            model = ANM(case["name"])
            model.buildHessian(
                coords, cutoff=cutoff, gamma=gamma, kdtree=False
            )
            network = np.asarray(model.getHessian(), dtype=float)
        else:
            raise ValueError("unknown model")
        model.calcModes(n_modes=n_modes)
        eigenvalues = np.asarray(model.getEigvals(), dtype=float)
        modes = np.asarray(model.getEigvecs(), dtype=float)
        msf = np.asarray(calcSqFlucts(model), dtype=float)
        correlation = np.asarray(calcCrossCorr(model), dtype=float)
    zero_count = int(np.sum(np.linalg.eigvalsh(network) < 1e-6))
    return {
        "name": case["name"],
        "result": {
            "model": model_name,
            "residue_mapping": mapping,
            "network_matrix": network.tolist(),
            "zero_mode_count": zero_count,
            "eigenvalues": eigenvalues.tolist(),
            "modes": modes.tolist(),
            "msf": msf.tolist(),
            "cross_correlation": correlation.tolist(),
        },
    }


def main():
    request = json.load(sys.stdin)
    json.dump(
        {"cases": [run_one(case) for case in request["cases"]]},
        sys.stdout, allow_nan=False, separators=(",", ":"),
    )


if __name__ == "__main__":
    main()

