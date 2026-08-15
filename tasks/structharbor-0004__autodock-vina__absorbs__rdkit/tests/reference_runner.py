#!/usr/bin/env python3
"""Root-only RDKit 2026.03.5 MMFF94 reference and packet builder."""

from __future__ import annotations

import json
import math
from pathlib import Path
import sys


REFERENCE_SITE = Path("/opt/reference-rdkit/python")
if REFERENCE_SITE.is_dir():
    sys.path.insert(0, str(REFERENCE_SITE))

from rdkit import Chem  # noqa: E402
from rdkit.Chem import AllChem  # noqa: E402


SCHEMA = "structharbor-vina-rdkit-mmff94-v1"
COMPONENTS = (
    "bond", "angle", "stretch_bend", "out_of_plane", "torsion",
    "van_der_waals", "electrostatic",
)
TERM_SETTERS = {
    "bond": "SetMMFFBondTerm",
    "angle": "SetMMFFAngleTerm",
    "stretch_bend": "SetMMFFStretchBendTerm",
    "out_of_plane": "SetMMFFOopTerm",
    "torsion": "SetMMFFTorsionTerm",
    "van_der_waals": "SetMMFFVdWTerm",
    "electrostatic": "SetMMFFEleTerm",
}


def prepare_molecule(spec):
    mol = Chem.MolFromSmiles(spec["smiles"])
    if mol is None:
        raise ValueError("invalid fixture SMILES")
    mol = Chem.AddHs(mol)
    params = AllChem.ETKDGv3()
    params.randomSeed = int(spec["seed"])
    params.useRandomCoords = False
    if AllChem.EmbedMolecule(mol, params) != 0:
        raise RuntimeError("RDKit fixture embedding failed")
    if not AllChem.MMFFHasAllMoleculeParams(mol):
        raise RuntimeError("fixture lacks MMFF94 parameters")
    AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94", maxIters=120)
    conf = mol.GetConformer()
    scale = float(spec["perturb"])
    for i in range(mol.GetNumAtoms()):
        point = conf.GetAtomPosition(i)
        point.x += scale * math.sin(0.73 * (i + 1) + 0.01 * spec["seed"])
        point.y += scale * math.cos(0.51 * (i + 2) - 0.02 * spec["seed"])
        point.z += scale * math.sin(0.37 * (i + 3) + 0.03 * spec["seed"])
        conf.SetAtomPosition(i, point)
    return mol


def properties(mol, spec):
    props = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant="MMFF94")
    if props is None:
        raise RuntimeError("RDKit MMFF94 property construction failed")
    props.SetMMFFDielectricModel(int(spec["dielectric_model"]))
    props.SetMMFFDielectricConstant(float(spec["dielectric_constant"]))
    return props


def component_energy(mol, spec, component):
    props = properties(mol, spec)
    for name, setter in TERM_SETTERS.items():
        getattr(props, setter)(name == component)
    field = AllChem.MMFFGetMoleculeForceField(
        mol, props, nonBondedThresh=100.0, confId=0,
        ignoreInterfragInteractions=True,
    )
    if field is None:
        raise RuntimeError("RDKit MMFF94 force-field construction failed")
    return float(field.CalcEnergy())


def atom_indices(record):
    return [int(value) for value in record]


def build_packet(mol, spec):
    props = properties(mol, spec)
    conf = mol.GetConformer()
    positions = [list(conf.GetAtomPosition(i)) for i in range(mol.GetNumAtoms())]
    packet = {
        "schema": SCHEMA,
        "positions": positions,
        "bonds": [],
        "angles": [],
        "stretch_bends": [],
        "out_of_plane": [],
        "torsions": [],
        "nonbonded": [],
    }

    for bond in mol.GetBonds():
        i, j = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        value = props.GetMMFFBondStretchParams(mol, i, j)
        if value is not None:
            packet["bonds"].append({
                "atoms": [i, j], "kb": value[1], "r0": value[2],
            })

    for j in range(mol.GetNumAtoms()):
        neighbors = [atom.GetIdx() for atom in mol.GetAtomWithIdx(j).GetNeighbors()]
        for first in range(len(neighbors)):
            for second in range(first + 1, len(neighbors)):
                i, k = neighbors[first], neighbors[second]
                angle = props.GetMMFFAngleBendParams(mol, i, j, k)
                if angle is None:
                    continue
                linear = abs(float(angle[2]) - 180.0) <= 1e-10
                packet["angles"].append({
                    "atoms": [i, j, k], "ka": angle[1],
                    "theta0": angle[2], "linear": linear,
                })
                if linear:
                    continue
                stretch = props.GetMMFFStretchBendParams(mol, i, j, k)
                first_bond = props.GetMMFFBondStretchParams(mol, i, j)
                second_bond = props.GetMMFFBondStretchParams(mol, j, k)
                if stretch is not None and first_bond is not None and second_bond is not None:
                    packet["stretch_bends"].append({
                        "atoms": [i, j, k],
                        "kba_ijk": stretch[1], "kba_kji": stretch[2],
                        "r0_ij": first_bond[2], "r0_jk": second_bond[2],
                        "theta0": angle[2],
                    })

    for j in range(mol.GetNumAtoms()):
        neighbors = [atom.GetIdx() for atom in mol.GetAtomWithIdx(j).GetNeighbors()]
        if len(neighbors) != 3:
            continue
        a, b, c = neighbors
        koop = props.GetMMFFOopBendParams(mol, a, j, b, c)
        if koop is None:
            continue
        for indices in ((a, j, b, c), (a, j, c, b), (b, j, c, a)):
            packet["out_of_plane"].append({
                "atoms": atom_indices(indices), "koop": koop,
            })

    query = Chem.MolFromSmarts("[!$(*#*)&!D1]~[!$(*#*)&!D1]")
    for j, k in mol.GetSubstructMatches(query, uniquify=True):
        j_atom, k_atom = mol.GetAtomWithIdx(j), mol.GetAtomWithIdx(k)
        allowed = (Chem.HybridizationType.SP2, Chem.HybridizationType.SP3)
        if j_atom.GetHybridization() not in allowed or k_atom.GetHybridization() not in allowed:
            continue
        for i_atom in j_atom.GetNeighbors():
            i = i_atom.GetIdx()
            if i == k:
                continue
            for l_atom in k_atom.GetNeighbors():
                l = l_atom.GetIdx()
                if l == j or l == i:
                    continue
                value = props.GetMMFFTorsionParams(mol, i, j, k, l)
                if value is not None:
                    packet["torsions"].append({
                        "atoms": [i, j, k, l],
                        "v1": value[1], "v2": value[2], "v3": value[3],
                    })

    distance_matrix = Chem.GetDistanceMatrix(mol, useBO=False, useAtomWts=False)
    dielectric = float(spec["dielectric_constant"])
    model = int(spec["dielectric_model"])
    for i in range(mol.GetNumAtoms()):
        for j in range(i + 1, mol.GetNumAtoms()):
            graph_distance = float(distance_matrix[i, j])
            if graph_distance < 3.0 or graph_distance >= 1e7:
                continue
            vdw = props.GetMMFFVdWParams(i, j)
            if vdw is None:
                continue
            packet["nonbonded"].append({
                "atoms": [i, j], "r_star": vdw[2], "epsilon": vdw[3],
                "charge_term": (
                    props.GetMMFFPartialCharge(i)
                    * props.GetMMFFPartialCharge(j) / dielectric
                ),
                "dielectric_model": model,
                "is_1_4": graph_distance == 3.0,
            })
    return packet


def run_one(spec):
    mol = prepare_molecule(spec)
    packet = build_packet(mol, spec)
    result = {name: component_energy(mol, spec, name) for name in COMPONENTS}
    result["total"] = sum(result.values())
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
