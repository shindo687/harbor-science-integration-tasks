#!/usr/bin/env python3
"""Root-only multi-frame adapter to locked native mkdssp 4.4.11."""

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
ATOMS = ("N", "CA", "C", "O")
STANDARD = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS",
    "ILE", "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP",
    "TYR", "VAL",
}


def validate(case):
    if case.get("schema") != "algobridge-gromacs-dssp-v1":
        raise ValueError("unsupported schema")
    cutoff = case.get("energy_cutoff")
    if (not isinstance(cutoff, (int, float)) or isinstance(cutoff, bool)
            or not math.isfinite(cutoff) or not -2.0 <= cutoff <= -0.1):
        raise ValueError("energy_cutoff must be finite and in [-2, -0.1]")
    topology = case.get("topology")
    frames = case.get("frames")
    if not isinstance(topology, list) or not 1 <= len(topology) <= 500:
        raise ValueError("topology must contain 1..500 residues")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 64:
        raise ValueError("frames must contain 1..64 entries")
    if len(topology) * len(frames) > 10000:
        raise ValueError("frame-residue product exceeds 10000")
    seen = set()
    for residue in topology:
        if not isinstance(residue, dict) or set(residue) != {
            "residue_name", "chain_id", "residue_index", "insertion_code"
        }:
            raise ValueError("invalid residue topology fields")
        if residue["residue_name"] not in STANDARD:
            raise ValueError("only the 20 standard amino acids are supported")
        chain = residue["chain_id"]
        number = residue["residue_index"]
        insertion = residue["insertion_code"]
        if not isinstance(chain, str) or len(chain) != 1 or not chain.isalnum():
            raise ValueError("chain_id must be one alphanumeric character")
        if (not isinstance(number, int) or isinstance(number, bool)
                or not -999 <= number <= 9999):
            raise ValueError("residue_index is invalid")
        if (not isinstance(insertion, str) or len(insertion) > 1
                or insertion and not insertion.isalnum()):
            raise ValueError("insertion_code is invalid")
        key = (chain, number, insertion)
        if key in seen:
            raise ValueError("duplicate residue identifier")
        seen.add(key)
    checked_frames = []
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != {
            "time_ps", "box_nm", "coordinates_nm"
        }:
            raise ValueError("invalid frame fields")
        time = frame["time_ps"]
        if (not isinstance(time, (int, float)) or isinstance(time, bool)
                or not math.isfinite(time)):
            raise ValueError("time_ps must be finite")
        box = frame["box_nm"]
        if (not isinstance(box, list) or len(box) != 3
                or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                       or not math.isfinite(v) or v < 0 for v in box)):
            raise ValueError("box_nm must contain three finite nonnegative values")
        periodic = all(v > 0 for v in box)
        if not periodic and any(v != 0 for v in box):
            raise ValueError("box dimensions must be all positive or all zero")
        if periodic and any(v < 0.4 for v in box):
            raise ValueError("periodic box dimensions must be at least 0.4 nm")
        groups = frame["coordinates_nm"]
        if not isinstance(groups, list) or len(groups) != len(topology):
            raise ValueError("coordinate residue count mismatch")
        checked_groups = []
        for group in groups:
            if (not isinstance(group, dict) or any(atom not in ATOMS for atom in group)
                    or not group):
                raise ValueError("coordinate group has invalid atom names")
            checked = {}
            for atom, xyz in group.items():
                if (not isinstance(xyz, list) or len(xyz) != 3
                        or any(not isinstance(v, (int, float)) or isinstance(v, bool)
                               or not math.isfinite(v) for v in xyz)):
                    raise ValueError("invalid atom coordinate")
                checked[atom] = [float(v) for v in xyz]
            checked_groups.append(checked)
        checked_frames.append({"time_ps": float(time),
                               "box_nm": [float(v) for v in box],
                               "coordinates_nm": checked_groups})
    return float(cutoff), topology, checked_frames


def nearest_image(value, anchor, box):
    if not all(box):
        return list(value)
    return [value[k] + round((anchor[k] - value[k]) / box[k]) * box[k]
            for k in range(3)]


def unwrap(topology, frame):
    output = []
    previous_c = None
    previous_chain = None
    for residue, raw in zip(topology, frame["coordinates_nm"]):
        if residue["chain_id"] != previous_chain:
            previous_c = None
        previous_chain = residue["chain_id"]
        if set(raw) != set(ATOMS):
            output.append({atom: [10*v for v in xyz] for atom, xyz in raw.items()})
            previous_c = None
            continue
        nitrogen = (nearest_image(raw["N"], previous_c, frame["box_nm"])
                    if previous_c is not None else list(raw["N"]))
        alpha = nearest_image(raw["CA"], nitrogen, frame["box_nm"])
        carbon = nearest_image(raw["C"], alpha, frame["box_nm"])
        oxygen = nearest_image(raw["O"], carbon, frame["box_nm"])
        output.append({atom: [10*v for v in xyz] for atom, xyz in (
            ("N", nitrogen), ("CA", alpha), ("C", carbon), ("O", oxygen)
        )})
        previous_c = carbon
    return output


def pdb_text(topology, coordinates):
    lines = ["HEADER    ALGOBRIDGE DSSP REFERENCE             01-JAN-00   TSK1"]
    serial = 1
    previous_chain = None
    for residue, atoms in zip(topology, coordinates):
        chain = residue["chain_id"]
        if previous_chain is not None and chain != previous_chain:
            lines.append("TER")
        previous_chain = chain
        number = residue["residue_index"]
        insertion = residue["insertion_code"] or " "
        name = residue["residue_name"]
        for atom in ATOMS:
            if atom not in atoms:
                continue
            x, y, z = atoms[atom]
            atom_field = f" {atom:<3}"
            lines.append(
                f"ATOM  {serial:5d} {atom_field:4s} {name:>3s} {chain:1s}"
                f"{number:4d}{insertion:1s}   {x:8.3f}{y:8.3f}{z:8.3f}"
                f"{1.00:6.2f}{0.00:6.2f}          {atom[0]:>2s}  "
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


def parse_output(path, topology):
    lines = path.read_text().splitlines()
    start = next(i for i, line in enumerate(lines)
                 if line.startswith("  #  RESIDUE")) + 1
    key_to_input = {
        (r["chain_id"], r["residue_index"], r["insertion_code"]): i
        for i, r in enumerate(topology)
    }
    rows = []
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
    n = len(topology)
    codes = ["C"] * n
    acceptor_index = [[-1, -1] for _ in range(n)]
    acceptor_energy = [[0.0, 0.0] for _ in range(n)]
    donor_index = [[-1, -1] for _ in range(n)]
    donor_energy = [[0.0, 0.0] for _ in range(n)]
    for line, number, i in rows:
        codes[i] = line[16] if line[16] in "HBEGITS" else "C"
        fields = (
            (acceptor_index, acceptor_energy, slice(38, 45), slice(46, 50), 0),
            (donor_index, donor_energy, slice(50, 56), slice(57, 61), 0),
            (acceptor_index, acceptor_energy, slice(61, 67), slice(68, 72), 1),
            (donor_index, donor_energy, slice(72, 78), slice(79, 83), 1),
        )
        for partners, energies, index_slice, energy_slice, rank in fields:
            partner, energy = parse_bond(
                line, index_slice, energy_slice, number, number_to_input)
            partners[i][rank] = partner
            energies[i][rank] = energy
    return {
        "secondary_structure": "".join(codes),
        "acceptor_index": acceptor_index,
        "acceptor_energy": acceptor_energy,
        "donor_index": donor_index,
        "donor_energy": donor_energy,
    }


def distance(first, second):
    return math.sqrt(sum((first[k] - second[k])**2 for k in range(3)))


def assign_with_cutoff(topology, coordinates, bonds, cutoff):
    """Reinterpret native mkdssp's top-two bond table at another cutoff."""
    n = len(topology)
    complete = [set(group) == set(ATOMS) for group in coordinates]
    internal = []
    counter = 0
    for i in range(n):
        counter += 1
        if (i and (not complete[i-1] or not complete[i]
                   or distance(coordinates[i-1].get("C", [0, 0, 0]),
                               coordinates[i].get("N", [99, 99, 99])) > 2.5)):
            counter += 1
        internal.append(counter)

    def uninterrupted(first, last):
        if (first < 0 or last >= n or first > last
                or topology[first]["chain_id"] != topology[last]["chain_id"]):
            return False
        return all(complete[i] for i in range(first, last+1)) and all(
            internal[i+1] - internal[i] == 1 for i in range(first, last))

    def has_bond(donor, acceptor):
        return any(bonds["acceptor_index"][donor][rank] == acceptor
                   and bonds["acceptor_energy"][donor][rank] < cutoff
                   for rank in (0, 1))

    def bridge_kind(i, j):
        if i == 0 or i+1 >= n or j == 0 or j+1 >= n:
            return None
        if not uninterrupted(i-1, i+1) or not uninterrupted(j-1, j+1):
            return None
        if ((has_bond(i+1, j) and has_bond(j, i-1))
                or (has_bond(j+1, i) and has_bond(i, j-1))):
            return "parallel"
        if ((has_bond(i+1, j-1) and has_bond(j+1, i-1))
                or (has_bond(j, i) and has_bond(i, j))):
            return "antiparallel"
        return None

    nearby = []
    for i in range(n-1):
        if not complete[i]:
            continue
        for j in range(i+1, n):
            if complete[j] and distance(coordinates[i]["CA"], coordinates[j]["CA"]) <= 9:
                nearby.append((i, j))
    bridges = []
    for i, j in nearby:
        kind = bridge_kind(i, j)
        if kind is None:
            continue
        attached = False
        for item in bridges:
            if item["kind"] != kind or i != item["i"][-1] + 1:
                continue
            if kind == "parallel" and j == item["j"][-1] + 1:
                item["i"].append(i); item["j"].append(j); attached = True; break
            if kind == "antiparallel" and j == item["j"][0] - 1:
                item["i"].append(i); item["j"].insert(0, j); attached = True; break
        if not attached:
            bridges.append({"kind": kind, "i": [i], "j": [j]})
    bridges.sort(key=lambda item: (topology[item["i"][0]]["chain_id"], item["i"][0]))
    a = 0
    while a < len(bridges):
        b = a + 1
        while b < len(bridges):
            left, right = bridges[a], bridges[b]
            ibi, iei = left["i"][0], left["i"][-1]
            jbi, jei = left["j"][0], left["j"][-1]
            ibj, iej = right["i"][0], right["i"][-1]
            jbj, jej = right["j"][0], right["j"][-1]
            skip = (left["kind"] != right["kind"]
                    or not uninterrupted(min(ibi, ibj), max(iei, iej))
                    or not uninterrupted(min(jbi, jbj), max(jei, jej))
                    or ibj < iei or ibj-iei >= 6 or (iei >= ibj and ibi <= iej))
            bulge = False
            if not skip and left["kind"] == "parallel" and jbj >= jei:
                bulge = ((jbj-jei < 6 and ibj-iei < 3) or jbj-jei < 3)
            elif not skip and jbi >= jej:
                bulge = ((jbi-jej < 6 and ibj-iei < 3) or jbi-jej < 3)
            if bulge:
                left["i"].extend(right["i"])
                left["j"] = (left["j"] + right["j"] if left["kind"] == "parallel"
                             else right["j"] + left["j"])
                bridges.pop(b)
            else:
                b += 1
        a += 1

    codes = ["C"] * n
    for item in bridges:
        code = "E" if len(item["i"]) > 1 else "B"
        for start, end in ((item["i"][0], item["i"][-1]),
                           (item["j"][0], item["j"][-1])):
            for i in range(start, end+1):
                if codes[i] != "E":
                    codes[i] = code
    flags = [[0] * n for _ in range(3)]
    for helix, stride in enumerate((3, 4, 5)):
        for i in range(n-stride):
            if uninterrupted(i, i+stride) and has_bond(i+stride, i):
                flags[helix][i+stride] = 2
                for middle in range(i+1, i+stride):
                    if flags[helix][middle] == 0:
                        flags[helix][middle] = 4
                flags[helix][i] = 3 if flags[helix][i] == 2 else 1
    bend = [False] * n
    for i in range(2, n-2):
        if (uninterrupted(i-2, i+2)
                and topology[i-2]["residue_index"] + 4 == topology[i+2]["residue_index"]):
            first = [coordinates[i]["CA"][k] - coordinates[i-2]["CA"][k] for k in range(3)]
            second = [coordinates[i+2]["CA"][k] - coordinates[i]["CA"][k] for k in range(3)]
            denominator = math.sqrt(sum(v*v for v in first) * sum(v*v for v in second))
            if denominator:
                cosine = max(-1, min(1, sum(a*b for a, b in zip(first, second))/denominator))
                bend[i] = math.degrees(math.acos(cosine)) > 70
    is_start = lambda value: value in (1, 3)
    for i in range(1, n-4):
        if is_start(flags[1][i]) and is_start(flags[1][i-1]):
            codes[i:i+4] = "H" * 4
    for i in range(1, n-3):
        if (is_start(flags[0][i]) and is_start(flags[0][i-1])
                and all(code in {"C", "G"} for code in codes[i:i+3])):
            codes[i:i+3] = "G" * 3
    for i in range(1, n-5):
        if (is_start(flags[2][i]) and is_start(flags[2][i-1])
                and all(code in {"C", "I", "H"} for code in codes[i:i+5])):
            codes[i:i+5] = "I" * 5
    for i in range(1, n-1):
        if codes[i] != "C" or not complete[i]:
            continue
        turn = any(i >= offset and is_start(flags[helix][i-offset])
                   for helix, stride in enumerate((3, 4, 5))
                   for offset in range(1, stride))
        if turn:
            codes[i] = "T"
        elif bend[i]:
            codes[i] = "S"
    return "".join(codes)


def run_frame(topology, frame, cutoff, root, frame_index):
    coordinates = unwrap(topology, frame)
    source = root / f"frame-{frame_index}.pdb"
    output = root / f"frame-{frame_index}.dssp"
    source.write_text(pdb_text(topology, coordinates))
    completed = subprocess.run(
        [MKDSSP, "--mmcif-dictionary", DICTIONARY, "--output-format", "dssp",
         str(source), str(output)], cwd=DATA_DIR, text=True, capture_output=True,
        timeout=60, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"mkdssp failed: {completed.stderr[-1200:]}")
    result = parse_output(output, topology)
    if cutoff != -0.5:
        result["secondary_structure"] = assign_with_cutoff(
            topology, coordinates, result, cutoff)
    result["time_ps"] = frame["time_ps"]
    result["complete_backbone"] = [set(group) == set(ATOMS) for group in coordinates]
    return result


def run_one(case):
    cutoff, topology, frames = validate(case)
    with tempfile.TemporaryDirectory(prefix="algobridge0011-dssp-") as directory:
        root = Path(directory)
        results = [run_frame(topology, frame, cutoff, root, i)
                   for i, frame in enumerate(frames)]
    keys = [f"{r['chain_id']}:{r['residue_index']}:{r['insertion_code']}"
            for r in topology]
    return {
        "schema": "algobridge-gromacs-dssp-result-v1",
        "energy_cutoff": cutoff,
        "residue_keys": keys,
        "frames": results,
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
