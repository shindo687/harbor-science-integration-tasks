#!/usr/bin/env python3
"""Materialize license-safe numbers from a locally licensed Rosetta run.

The output contains coordinates, generic clean-room atom parameters, and
InterfaceAnalyzer scalar results.  It never copies Rosetta code or databases.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


WORK = Path("/tmp/structharbor-0006-upstream.St5A6X")
SOURCE_PDB = Path("/home/xjtan/antibody_design/datasets/reference/snac_db/v2.1/expanded/benchmark/ab_complexes/ab_complexes/8ZR4-ASU1-VH_L-VL_M-Ag_N.pdb")
OUTPUT = Path(__file__).resolve().parents[1] / "tests" / "rosetta-calibration.json"
DIRECTION = [0.853619127452, -0.284546865078, 0.436311204099]
ELEMENTS = {
    "C": (4.08, 0.10, 1.70),
    "N": (3.90, 0.08, 1.55),
    "O": (3.60, 0.12, 1.52),
    "S": (4.32, 0.20, 1.80),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atom_charge(residue: str, atom: str) -> float:
    if residue in {"ASP", "GLU"} and atom.startswith("O"):
        return -0.45
    if residue == "ARG" and atom in {"NE", "NH1", "NH2"}:
        return 0.30
    if residue == "LYS" and atom == "NZ":
        return 0.70
    return 0.0


def packet(path: Path) -> dict:
    atoms = []
    for line in path.read_text().splitlines():
        if not line.startswith("ATOM  "):
            continue
        atom_name = line[12:16].strip()
        residue_name = line[17:20].strip()
        residue_number = line[22:26].strip()
        chain = line[21]
        element = line[76:78].strip() or atom_name[0]
        sigma, epsilon, radius = ELEMENTS[element]
        atoms.append({
            "id": f"{chain}:{residue_number}:{atom_name}",
            "chain": chain,
            "residue": f"{residue_name}{residue_number}",
            "coord": [float(line[offset:offset + 8]) for offset in (30, 38, 46)],
            "sigma": sigma,
            "epsilon": epsilon,
            "charge": atom_charge(residue_name, atom_name),
            "sasa_radius": radius,
            "donor_direction": None,
            "acceptor_direction": None,
        })
    return {
        "name": f"rosetta_8zr4_fragment_{path.stem}",
        "atoms": atoms,
        "group_a": ["H"],
        "group_b": ["A"],
        "separation_distance": 40.0,
        "separation_direction": DIRECTION,
        "parameters": {
            "cutoff": 10.0,
            "switch_distance": 8.0,
            "dielectric": 40.0,
            "probe_radius": 1.4,
            "solvation_gamma": 0.005,
            "hbond_strength": 1.5,
            "hbond_distance": 2.9,
            "hbond_width": 0.45,
        },
        "compute_forces": False,
    }


def score(path: Path) -> dict:
    values = None
    for line in path.read_text().splitlines():
        fields = line.split()
        if fields[:1] == ["SCORE:"] and len(fields) > 20 and fields[1] != "total_score":
            try:
                if fields[2] != "-nan":
                    values = {
                        "dG_separated": float(fields[5]),
                        "dSASA_int": float(fields[8]),
                        "hbonds_int": float(fields[13]),
                    }
            except ValueError:
                pass
    if values is None:
        raise RuntimeError(f"no usable score row in {path}")
    return values


def main() -> None:
    cases = []
    for pdb in sorted((WORK / "fragment_calibration").glob("*.pdb")):
        result = score(WORK / "fragment_calibration" / "results" / pdb.stem / "score-new.sc")
        cases.append({"packet": packet(pdb), "rosetta": result, "pdb_sha256": sha256(pdb)})
    document = {
        "schema_version": 1,
        "purpose": "ranking-only calibration; not numerical Ref2015 reproduction",
        "source_structure": {
            "id": "8ZR4",
            "file_sha256": sha256(SOURCE_PDB),
            "fragment_sha256": sha256(WORK / "fragment.pdb"),
            "chains": ["H", "A"],
            "residues": ["H:109-115", "A:263-269"],
        },
        "rosetta_runtime": {
            "release": "2025.03+release.1f5080a079",
            "application": "InterfaceAnalyzer.cxx11threadserialization.linuxclangrelease",
            "binary_sha256": "723b3ba5a969708c1a32b877ab56e94ebb34cba587c18ba0cf2e45a695cb6857",
            "binary_size": 296856,
            "weights": "ref2015",
            "interface": "H_A",
            "pack_input": False,
            "pack_separated": False,
            "constant_seed": 80616,
        },
        "cases": cases,
    }
    OUTPUT.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(OUTPUT, sha256(OUTPUT), len(cases))


if __name__ == "__main__":
    main()
