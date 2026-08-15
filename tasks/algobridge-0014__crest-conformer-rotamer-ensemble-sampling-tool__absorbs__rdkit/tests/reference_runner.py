#!/usr/bin/env python3
"""Root-only RDKit ETKDGv3 reference and bounded-packet builder."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys


REFERENCE_SITE = Path("/opt/reference-rdkit/python")
if REFERENCE_SITE.is_dir():
    sys.path.insert(0, str(REFERENCE_SITE))

from rdkit import Chem  # noqa: E402
from rdkit.Chem import AllChem, rdDistGeom  # noqa: E402


SCHEMA = "algobridge-crest-etkdg-bounded-v1"


def coordinates(mol, conf_id):
    conf = mol.GetConformer(int(conf_id))
    return [[float(value) for value in conf.GetAtomPosition(i)]
            for i in range(mol.GetNumAtoms())]


def volume(coords, center, neighbors):
    def sub(first, second):
        return [first[i] - second[i] for i in range(3)]

    def cross(first, second):
        return [first[1]*second[2] - first[2]*second[1],
                first[2]*second[0] - first[0]*second[2],
                first[0]*second[1] - first[1]*second[0]]

    origin = coords[center]
    first, second, third = [sub(coords[i], origin) for i in neighbors]
    normal = cross(second, third)
    return sum(first[i] * normal[i] for i in range(3))


def distance_matrix(coords, indices):
    result = []
    for first in range(len(indices)):
        row = []
        for second in range(len(indices)):
            a, b = coords[indices[first]], coords[indices[second]]
            row.append(math.sqrt(sum((a[k] - b[k]) ** 2 for k in range(3))))
        result.append(row)
    return result


def make_molecule(spec):
    mol = Chem.MolFromSmiles(spec["smiles"])
    if mol is None:
        raise ValueError("invalid fixture SMILES")
    mol = Chem.AddHs(mol)
    if sum(atom.GetAtomicNum() > 1 for atom in mol.GetAtoms()) > 64:
        raise ValueError("fixture exceeds bounded heavy-atom limit")
    return mol


def native_ensemble(mol, spec):
    params = AllChem.ETKDGv3()
    params.randomSeed = int(spec["seed"])
    params.numThreads = 1
    params.pruneRmsThresh = float(spec["prune_rms"])
    params.enforceChirality = True
    params.useRandomCoords = False
    params.maxIterations = 2000
    ids = list(AllChem.EmbedMultipleConfs(
        mol, numConfs=int(spec["num_confs"]), params=params,
    ))
    if not ids:
        raise RuntimeError("native ETKDG fixture embedding failed")
    return ids


def bounds_matrices(mol):
    params = AllChem.ETKDGv3()
    raw = rdDistGeom.GetMoleculeBoundsMatrix(
        mol, params, doTriangleSmoothing=False, scaleVDW=False,
        set15bounds=True, set14bounds=True, set13bounds=True,
    )
    smooth = rdDistGeom.GetMoleculeBoundsMatrix(
        mol, params, doTriangleSmoothing=True, scaleVDW=False,
        set15bounds=True, set14bounds=True, set13bounds=True,
    )
    n = mol.GetNumAtoms()

    def split(matrix):
        lower = [[0.0] * n for _ in range(n)]
        upper = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                lower[i][j] = lower[j][i] = float(matrix[j, i])
                upper[i][j] = upper[j][i] = float(matrix[i, j])
        return lower, upper

    return split(raw), split(smooth)


def run_one(spec):
    mol = make_molecule(spec)
    ids = native_ensemble(mol, spec)
    native_coords = [coordinates(mol, conf_id) for conf_id in ids]
    (raw_lower, raw_upper), (smooth_lower, smooth_upper) = bounds_matrices(mol)
    heavy = [atom.GetIdx() for atom in mol.GetAtoms() if atom.GetAtomicNum() > 1]
    pair_bounds = []
    for i in range(mol.GetNumAtoms()):
        for j in range(i + 1, mol.GetNumAtoms()):
            pair_bounds.append({
                "atoms": [i, j], "lower": raw_lower[i][j],
                "upper": raw_upper[i][j],
            })
    chiral = []
    for center, _label in Chem.FindMolChiralCenters(
            mol, includeUnassigned=False, useLegacyImplementation=False):
        neighbors = sorted(atom.GetIdx() for atom in mol.GetAtomWithIdx(center).GetNeighbors())[:3]
        if len(neighbors) != 3:
            continue
        signed = volume(native_coords[0], center, neighbors)
        chiral.append({
            "center": int(center), "neighbors": neighbors,
            "sign": 1 if signed >= 0 else -1,
            "min_volume": min(0.20, max(0.02, abs(signed) * 0.15)),
        })
    packet = {
        "schema": SCHEMA,
        "atomic_numbers": [atom.GetAtomicNum() for atom in mol.GetAtoms()],
        "pair_bounds": pair_bounds,
        "chiral_constraints": chiral,
        "prune_atoms": heavy,
        "num_confs": int(spec["num_confs"]),
        "seed": int(spec["seed"]),
        "prune_rms": float(spec["prune_rms"]),
        "max_attempts": int(spec["num_confs"]) * 12,
    }
    result = {
        "smoothed_lower": smooth_lower,
        "smoothed_upper": smooth_upper,
        "native_conformers": native_coords,
        "native_distance_matrices": [distance_matrix(value, heavy) for value in native_coords],
        "native_count": len(native_coords),
    }
    return {"name": spec["name"], "packet": packet, "result": result}


def main():
    request = json.load(sys.stdin)
    response = []
    for spec in request["cases"]:
        try:
            response.append(run_one(spec))
        except Exception as exc:
            response.append({"name": spec.get("name"), "error": type(exc).__name__})
    json.dump({"cases": response}, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
