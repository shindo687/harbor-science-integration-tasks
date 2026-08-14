#!/usr/bin/env python3
"""Root-only adapter from the task protocol to the locked native mkdssp."""

from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile


MKDSSP = "/opt/dssp/bin/mkdssp"
DATA_DIR = "/opt/dssp/share/libcifpp"
DICTIONARY = f"{DATA_DIR}/mmcif_pdbx.dic"
ONE_TO_THREE = (
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
)


def validate(case):
    if case.get("schema") != "structharbor-af2-dssp-v1":
        raise ValueError("unsupported schema")
    residues = case.get("residues")
    if not isinstance(residues, list) or not 1 <= len(residues) <= 1000:
        raise ValueError("residues must contain 1..1000 entries")
    seen = set()
    for residue in residues:
        if residue.get("residue_name") not in ONE_TO_THREE:
            raise ValueError("only the 20 standard amino acids are supported")
        chain = residue.get("chain_id")
        number = residue.get("residue_index")
        insertion = residue.get("insertion_code", "")
        if not isinstance(chain, str) or len(chain) != 1 or not chain.isalnum():
            raise ValueError("chain_id must be one alphanumeric character")
        if not isinstance(number, int) or isinstance(number, bool) or not -999 <= number <= 9999:
            raise ValueError("residue_index is invalid")
        if not isinstance(insertion, str) or len(insertion) > 1:
            raise ValueError("insertion_code is invalid")
        key = (chain, number, insertion)
        if key in seen:
            raise ValueError("duplicate residue identifier")
        seen.add(key)
        atoms = residue.get("atoms")
        if not isinstance(atoms, dict) or set(atoms) != {"N", "CA", "C", "O"}:
            raise ValueError("each residue needs exactly N, CA, C, and O")
        for xyz in atoms.values():
            if (not isinstance(xyz, list) or len(xyz) != 3
                    or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                           or not math.isfinite(v) for v in xyz)):
                raise ValueError("invalid atom coordinate")
    return residues


def pdb_text(residues):
    lines = ["HEADER    STRUCTHARBOR DSSP REFERENCE             01-JAN-00   TSK1"]
    serial = 1
    for residue in residues:
        chain = residue["chain_id"]
        number = residue["residue_index"]
        insertion = residue.get("insertion_code", "") or " "
        name = residue["residue_name"]
        for atom in ("N", "CA", "C", "O"):
            x, y, z = residue["atoms"][atom]
            atom_field = f" {atom:<3}" if len(atom) < 4 else atom
            element = atom[0]
            lines.append(
                f"ATOM  {serial:5d} {atom_field:4s} {name:>3s} {chain:1s}"
                f"{number:4d}{insertion:1s}   {x:8.3f}{y:8.3f}{z:8.3f}"
                f"{1.00:6.2f}{0.00:6.2f}          {element:>2s}  "
            )
            serial += 1
    lines.extend(["TER", "END"])
    return "\n".join(lines) + "\n"


def parse_bond(line, index_slice, energy_slice, current_number, number_to_input):
    relative = int(line[index_slice].strip() or "0")
    energy = float(line[energy_slice].strip() or "0")
    if relative == 0 and energy == 0.0:
        return -1, 0.0
    return number_to_input.get(current_number + relative, -1), energy


def parse_output(path, residues):
    lines = path.read_text().splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("  #  RESIDUE")) + 1
    except StopIteration as exc:
        raise RuntimeError("mkdssp output has no residue table") from exc
    rows = []
    key_to_input = {
        (r["chain_id"], r["residue_index"], r.get("insertion_code", "")): i
        for i, r in enumerate(residues)
    }
    number_to_input = {}
    for line in lines[start:]:
        if len(line) < 84 or line[13] == "!":
            continue
        number = int(line[0:5])
        key = (line[11].strip() or "A", int(line[5:10]), line[10].strip())
        if key not in key_to_input:
            raise RuntimeError(f"mkdssp returned unknown residue {key!r}")
        input_index = key_to_input[key]
        number_to_input[number] = input_index
        rows.append((line, number, input_index))
    if len(rows) != len(residues):
        raise RuntimeError(f"mkdssp returned {len(rows)} of {len(residues)} residues")

    codes = ["C"] * len(residues)
    acceptor_index = [[-1, -1] for _ in residues]
    acceptor_energy = [[0.0, 0.0] for _ in residues]
    donor_index = [[-1, -1] for _ in residues]
    donor_energy = [[0.0, 0.0] for _ in residues]
    for line, number, i in rows:
        code = line[16]
        codes[i] = code if code in "HBEGITS" else "C"
        fields = (
            (acceptor_index, acceptor_energy, slice(38, 45), slice(46, 50), 0),
            (donor_index, donor_energy, slice(50, 56), slice(57, 61), 0),
            (acceptor_index, acceptor_energy, slice(61, 67), slice(68, 72), 1),
            (donor_index, donor_energy, slice(72, 78), slice(79, 83), 1),
        )
        for partners, energies, index_slice, energy_slice, rank in fields:
            partner, energy = parse_bond(
                line, index_slice, energy_slice, number, number_to_input
            )
            partners[i][rank] = partner
            energies[i][rank] = energy
    return {
        "secondary_structure": codes,
        "acceptor_index": acceptor_index,
        "acceptor_energy": acceptor_energy,
        "donor_index": donor_index,
        "donor_energy": donor_energy,
    }


def run_one(case):
    residues = validate(case)
    with tempfile.TemporaryDirectory(prefix="structharbor-dssp-") as tmp:
        tmp = Path(tmp)
        source = tmp / "input.pdb"
        output = tmp / "output.dssp"
        source.write_text(pdb_text(residues))
        completed = subprocess.run(
            [MKDSSP, "--mmcif-dictionary", DICTIONARY, "--output-format", "dssp",
             str(source), str(output)],
            cwd=DATA_DIR, text=True, capture_output=True, timeout=60, check=False,
        )
        if completed.returncode:
            raise RuntimeError(f"mkdssp failed: {completed.stderr[-1200:]}")
        return parse_output(output, residues)


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
