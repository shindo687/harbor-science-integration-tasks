#!/usr/bin/env python3
"""Deterministic real-structure cases for STRUCTHARBOR-0003."""

from __future__ import annotations

import copy
import math
from pathlib import Path


FIXTURES = Path(__file__).with_name("fixtures")
STANDARD = {
    "ALA": 0, "ARG": 1, "ASN": 2, "ASP": 3, "CYS": 4,
    "GLN": 5, "GLU": 6, "GLY": 7, "HIS": 8, "ILE": 9,
    "LEU": 10, "LYS": 11, "MET": 12, "PHE": 13, "PRO": 14,
    "SER": 15, "THR": 16, "TRP": 17, "TYR": 18, "VAL": 19,
}


def load_backbone(pdb_id: str):
    """Read first-model, standard-residue backbone atoms from a locked PDB."""
    residues = {}
    order = []
    for line in (FIXTURES / f"{pdb_id}.pdb").read_text().splitlines():
        if line.startswith("ENDMDL"):
            break
        if not line.startswith("ATOM  "):
            continue
        atom = line[12:16].strip()
        altloc = line[16]
        name = line[17:20].strip()
        if atom not in {"N", "CA", "C", "O"} or altloc not in {" ", "A"}:
            continue
        if name not in STANDARD:
            continue
        chain = line[21].strip() or "A"
        number = int(line[22:26])
        insertion = line[26].strip()
        key = (chain, number, insertion)
        if key not in residues:
            residues[key] = {
                "residue_name": name,
                "chain_id": chain,
                "residue_index": number,
                "insertion_code": insertion,
                "atoms": {},
            }
            order.append(key)
        # Prefer the blank conformer; otherwise retain the first A conformer.
        if atom not in residues[key]["atoms"] or altloc == " ":
            residues[key]["atoms"][atom] = [
                float(line[30:38]), float(line[38:46]), float(line[46:54])
            ]
    result = [residues[key] for key in order]
    return [r for r in result if set(r["atoms"]) == {"N", "CA", "C", "O"}]


def _rotation(axis, degrees):
    x, y, z = axis
    length = math.sqrt(x * x + y * y + z * z)
    x, y, z = x / length, y / length, z / length
    angle = math.radians(degrees)
    c, s, t = math.cos(angle), math.sin(angle), 1.0 - math.cos(angle)
    return (
        (t*x*x+c, t*x*y-s*z, t*x*z+s*y),
        (t*x*y+s*z, t*y*y+c, t*y*z-s*x),
        (t*x*z-s*y, t*y*z+s*x, t*z*z+c),
    )


def transform(residues, *, axis=(1.0, 2.0, 3.0), degrees=0.0,
              shift=(0.0, 0.0, 0.0), jitter=0.0):
    result = copy.deepcopy(residues)
    matrix = _rotation(axis, degrees)
    for i, residue in enumerate(result):
        for j, atom in enumerate(("N", "CA", "C", "O")):
            xyz = residue["atoms"][atom]
            rotated = [sum(matrix[row][col] * xyz[col] for col in range(3))
                       for row in range(3)]
            residue["atoms"][atom] = [
                round(rotated[k] + shift[k]
                      + jitter * math.sin((i + 1) * 17 + (j + 1) * 7 + k), 3)
                for k in range(3)
            ]
    return result


def rechain(residues, boundaries, *, separate=False):
    result = copy.deepcopy(residues)
    boundaries = sorted(boundaries)
    for i, residue in enumerate(result):
        chain = sum(i >= boundary for boundary in boundaries)
        residue["chain_id"] = chr(ord("A") + chain)
        residue["residue_index"] = i - (boundaries[chain - 1] if chain else 0) + 1
        residue["insertion_code"] = ""
        if separate and chain:
            for atom, xyz in residue["atoms"].items():
                residue["atoms"][atom] = [xyz[0] + 35.0 * chain, xyz[1], xyz[2]]
    return result


def combine(first, second, *, distance=40.0):
    left = rechain(first, [], separate=False)
    right = transform(rechain(second, [], separate=False), shift=(distance, 3.0, -5.0))
    for residue in left:
        residue["chain_id"] = "A"
    for residue in right:
        residue["chain_id"] = "B"
    return left + right


def case(name, residues):
    return {
        "name": name,
        "schema": "structharbor-af2-dssp-v1",
        "residues": copy.deepcopy(residues),
    }


def public_cases():
    crn = load_backbone("1CRN")
    zdd = load_backbone("1ZDD")
    ten = load_backbone("1TEN")
    return [
        case("public_crambin_mixed", crn),
        case("public_zdd_helical", zdd),
        case("public_ten_beta", ten),
        case("public_crambin_rigid_transform",
             transform(crn, axis=(2, -1, 4), degrees=73, shift=(18, -9, 5))),
        case("public_two_chain_mixed", combine(zdd[:28], ten[8:48], distance=45)),
    ]


def hidden_cases():
    crn = load_backbone("1CRN")
    zdd = load_backbone("1ZDD")
    ten = load_backbone("1TEN")
    return [
        case("hidden_crambin_original", crn),
        case("hidden_zdd_original", zdd),
        case("hidden_ten_original", ten),
        case("hidden_crambin_crop", crn[4:42]),
        case("hidden_zdd_crop", zdd[2:31]),
        case("hidden_ten_n_terminal", ten[:58]),
        case("hidden_ten_c_terminal", ten[27:]),
        case("hidden_ten_rotated",
             transform(ten, axis=(-3, 1, 2), degrees=121, shift=(-24, 11, 37))),
        case("hidden_zdd_rotated",
             transform(zdd, axis=(1, 5, -2), degrees=39, shift=(7, -31, 12))),
        case("hidden_crambin_small_jitter", transform(crn, jitter=0.004)),
        case("hidden_ten_small_jitter", transform(ten, jitter=0.003)),
        case("hidden_crambin_chain_split", rechain(crn, [22], separate=False)),
        case("hidden_ten_three_chains", rechain(ten, [31, 63], separate=True)),
        case("hidden_two_chain_helical_beta", combine(zdd, ten[12:70], distance=52)),
        case("hidden_two_chain_mixed", combine(crn[3:39], ten[4:62], distance=38)),
    ]

