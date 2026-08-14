#!/usr/bin/env python3
"""Deterministic multi-frame GROMACS/DSSP fixtures for ALGOBRIDGE-0011."""

from __future__ import annotations

import copy
import math
from pathlib import Path


FIXTURES = Path(__file__).with_name("fixtures")
STANDARD = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS",
    "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP",
    "TYR", "VAL",
}
ATOMS = ("N", "CA", "C", "O")


def load_backbone(pdb_id):
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
        if atom not in ATOMS or altloc not in {" ", "A"} or name not in STANDARD:
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
        if atom not in residues[key]["atoms"] or altloc == " ":
            residues[key]["atoms"][atom] = [
                float(line[30:38]), float(line[38:46]), float(line[46:54])
            ]
    return [residues[key] for key in order
            if set(residues[key]["atoms"]) == set(ATOMS)]


def _rotation(axis, degrees):
    x, y, z = axis
    length = math.sqrt(x*x + y*y + z*z)
    x, y, z = x/length, y/length, z/length
    angle = math.radians(degrees)
    c, s, t = math.cos(angle), math.sin(angle), 1-math.cos(angle)
    return (
        (t*x*x+c, t*x*y-s*z, t*x*z+s*y),
        (t*x*y+s*z, t*y*y+c, t*y*z-s*x),
        (t*x*z-s*y, t*y*z+s*x, t*z*z+c),
    )


def transform(residues, *, axis=(1, 2, 3), degrees=0, shift=(0, 0, 0),
              jitter=0.0):
    result = copy.deepcopy(residues)
    matrix = _rotation(axis, degrees)
    for i, residue in enumerate(result):
        for j, atom in enumerate(ATOMS):
            if atom not in residue["atoms"]:
                continue
            xyz = residue["atoms"][atom]
            rotated = [sum(matrix[row][column] * xyz[column]
                           for column in range(3)) for row in range(3)]
            residue["atoms"][atom] = [
                round(rotated[k] + shift[k]
                      + jitter * math.sin((i+1)*17 + (j+1)*7 + k), 3)
                for k in range(3)
            ]
    return result


def rechain(residues, boundaries, *, separate=False):
    result = copy.deepcopy(residues)
    boundaries = sorted(boundaries)
    for i, residue in enumerate(result):
        chain = sum(i >= boundary for boundary in boundaries)
        residue["chain_id"] = chr(ord("A") + chain)
        start = boundaries[chain-1] if chain else 0
        residue["residue_index"] = i - start + 1
        residue["insertion_code"] = ""
        if separate and chain:
            for xyz in residue["atoms"].values():
                xyz[0] += 35.0 * chain
    return result


def combine(first, second, distance=40.0):
    left = rechain(first, [])
    right = transform(rechain(second, []), shift=(distance, 3, -5))
    for residue in left:
        residue["chain_id"] = "A"
    for residue in right:
        residue["chain_id"] = "B"
    return left + right


def missing_atom(residues, residue_index, atom):
    result = copy.deepcopy(residues)
    del result[residue_index]["atoms"][atom]
    return result


def _topology(residues):
    return [{key: residue[key] for key in (
        "residue_name", "chain_id", "residue_index", "insertion_code"
    )} for residue in residues]


def _frame(residues, time_ps, box_nm=None, wrap=False):
    box = [0.0, 0.0, 0.0] if box_nm is None else [float(v) for v in box_nm]
    coordinates = []
    for residue in residues:
        atoms = {}
        for atom, xyz_angstrom in residue["atoms"].items():
            xyz = [value / 10.0 for value in xyz_angstrom]
            if wrap:
                xyz = [xyz[k] % box[k] for k in range(3)]
            atoms[atom] = xyz
        coordinates.append(atoms)
    return {"time_ps": float(time_ps), "box_nm": box,
            "coordinates_nm": coordinates}


def case(name, frames, *, energy_cutoff=-0.5, boxes=None, wraps=None):
    if boxes is None:
        boxes = [None] * len(frames)
    if wraps is None:
        wraps = [False] * len(frames)
    topology = _topology(frames[0])
    for frame in frames[1:]:
        if _topology(frame) != topology:
            raise ValueError("all frames must share residue topology")
    return {
        "name": name,
        "schema": "algobridge-gromacs-dssp-v1",
        "energy_cutoff": energy_cutoff,
        "topology": topology,
        "frames": [_frame(frame, i * 2.5, box, wrap)
                   for i, (frame, box, wrap) in enumerate(zip(frames, boxes, wraps))],
    }


def public_cases():
    crn = load_backbone("1CRN")
    zdd = load_backbone("1ZDD")
    ten = load_backbone("1TEN")
    return [
        case("public_crambin_mixed", [crn]),
        case("public_zdd_multiframe", [
            zdd,
            transform(zdd, axis=(2, -1, 4), degrees=73, shift=(18, -9, 5)),
            transform(zdd, jitter=0.003),
        ]),
        case("public_ten_beta", [ten]),
        case("public_crambin_pbc", [crn], boxes=[[2.8, 3.1, 3.3]], wraps=[True]),
        case("public_two_chain_mixed", [combine(zdd[:28], ten[8:48], 45)]),
    ]


def hidden_cases():
    crn = load_backbone("1CRN")
    zdd = load_backbone("1ZDD")
    ten = load_backbone("1TEN")
    crn_rotated = transform(crn, axis=(-3, 1, 2), degrees=121,
                            shift=(-24, 11, 37))
    ten_rotated = transform(ten, axis=(1, 5, -2), degrees=39,
                            shift=(7, -31, 12))
    return [
        case("hidden_crambin_original", [crn]),
        case("hidden_zdd_original", [zdd]),
        case("hidden_ten_original", [ten]),
        case("hidden_crambin_three_frames", [crn, crn_rotated,
             transform(crn, jitter=0.004)]),
        case("hidden_ten_two_frames", [ten, ten_rotated]),
        case("hidden_crambin_rigid", [crn_rotated]),
        case("hidden_ten_rigid", [ten_rotated]),
        case("hidden_zdd_pbc", [zdd], boxes=[[2.6, 2.9, 3.2]], wraps=[True]),
        case("hidden_crambin_pbc_multiframe", [crn, crn_rotated],
             boxes=[[2.8, 3.1, 3.3], [2.8, 3.1, 3.3]], wraps=[True, True]),
        case("hidden_missing_oxygen", [missing_atom(crn, 20, "O")]),
        case("hidden_missing_nitrogen", [missing_atom(ten[:70], 35, "N")]),
        case("hidden_crambin_chain_split", [rechain(crn, [22])]),
        case("hidden_ten_three_chains", [rechain(ten, [31, 63], separate=True)]),
        case("hidden_two_chain_helical_beta", [combine(zdd, ten[12:70], 52)]),
        case("hidden_stricter_cutoff", [crn], energy_cutoff=-1.5),
    ]


def invalid_cases():
    base = public_cases()[0]
    result = []

    def add(name, edit):
        value = copy.deepcopy(base)
        value["name"] = name
        edit(value)
        result.append(value)

    add("invalid_schema", lambda x: x.update(schema="wrong"))
    add("invalid_empty_topology", lambda x: x.update(topology=[]))
    add("invalid_duplicate_key", lambda x: x["topology"].__setitem__(1, copy.deepcopy(x["topology"][0])))
    add("invalid_residue_name", lambda x: x["topology"][0].update(residue_name="MSE"))
    add("invalid_empty_frames", lambda x: x.update(frames=[]))
    add("invalid_frame_length", lambda x: x["frames"][0]["coordinates_nm"].pop())
    add("invalid_box_partial", lambda x: x["frames"][0].update(box_nm=[2.0, 0.0, 2.0]))
    add("invalid_coordinate", lambda x: x["frames"][0]["coordinates_nm"][0]["N"].__setitem__(0, "nan"))
    add("invalid_unknown_atom", lambda x: x["frames"][0]["coordinates_nm"][0].update(CB=[0, 0, 0]))
    add("invalid_cutoff", lambda x: x.update(energy_cutoff=0.0))
    return result
