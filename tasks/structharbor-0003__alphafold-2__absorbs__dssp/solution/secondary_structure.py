"""Backbone-only DSSP-compatible assignment for AlphaFold output arrays.

This module is intentionally self-contained: it uses only NumPy and the native
AlphaFold atom/sequence encodings, and never invokes an external executable.
"""

from __future__ import annotations

import math

import numpy as np


_N, _CA, _C, _O = 0, 1, 2, 4
_PROLINE = 14
_MAX_CA_DISTANCE = 9.0
_MAX_PEPTIDE_DISTANCE = 2.5
_BOND_THRESHOLD = -0.5
_MIN_ENERGY = -9.9
_COUPLING = -27.888


def _inputs(atom_positions, atom_mask, aatype, residue_index, chain_index):
    positions = np.asarray(atom_positions, dtype=float)
    mask = np.asarray(atom_mask, dtype=float)
    kinds = np.asarray(aatype)
    numbers = np.asarray(residue_index)
    if chain_index is None:
        chains = np.zeros(kinds.shape, dtype=np.int64)
    else:
        chains = np.asarray(chain_index)
    if positions.ndim != 3 or positions.shape[1:] != (37, 3):
        raise ValueError("atom_positions must have shape [N, 37, 3]")
    n = positions.shape[0]
    if not 1 <= n <= 1000:
        raise ValueError("N must be in the range 1..1000")
    if mask.shape != (n, 37):
        raise ValueError("atom_mask must have shape [N, 37]")
    for name, value in (("aatype", kinds), ("residue_index", numbers),
                        ("chain_index", chains)):
        if value.shape != (n,) or value.dtype.kind not in "iu":
            raise ValueError(f"{name} must be an integer [N] array")
    kinds = kinds.astype(np.int64, copy=False)
    numbers = numbers.astype(np.int64, copy=False)
    chains = chains.astype(np.int64, copy=False)
    if np.any((kinds < 0) | (kinds >= 20)):
        raise ValueError("aatype must contain the 20 standard AlphaFold indices")
    if np.any(chains < 0):
        raise ValueError("chain_index must be non-negative")
    required = np.array([_N, _CA, _C, _O])
    if not np.all(np.isfinite(mask)) or not np.all(mask[:, required] > 0.5):
        raise ValueError("every residue must contain N, CA, C, and O")
    backbone = positions[:, required]
    if not np.all(np.isfinite(backbone)):
        raise ValueError("backbone coordinates must be finite")
    if len(set(zip(chains.tolist(), numbers.tolist()))) != n:
        raise ValueError("residue identifiers must be unique within each chain")
    return positions, kinds, numbers, chains


def _distance(a, b):
    return float(np.linalg.norm(a - b))


def _round_milli(value):
    scaled = value * 1000.0
    if scaled >= 0:
        return math.floor(scaled + 0.5) / 1000.0
    return math.ceil(scaled - 0.5) / 1000.0


def assign_secondary_structure(atom_positions, atom_mask, aatype,
                               residue_index, chain_index=None):
    """Assign 8-state secondary structure and the two best backbone H-bonds.

    Args are AlphaFold all-atom arrays.  The returned partner indices are
    zero-based positions in those arrays, with ``-1`` representing no partner.
    ``secondary_structure`` uses H/B/E/G/I/T/S/C; the DSSP extension P is
    deliberately normalized to C.
    """
    xyz, kinds, sequence_numbers, chains = _inputs(
        atom_positions, atom_mask, aatype, residue_index, chain_index
    )
    n = len(kinds)
    nitrogen = xyz[:, _N]
    alpha_carbon = xyz[:, _CA]
    carbon = xyz[:, _C]
    oxygen = xyz[:, _O]

    # Native DSSP numbers contain a vacant slot at a geometric chain break.
    internal = np.empty(n, dtype=np.int64)
    counter = 0
    for i in range(n):
        counter += 1
        if i and _distance(carbon[i - 1], nitrogen[i]) > _MAX_PEPTIDE_DISTANCE:
            counter += 1
        internal[i] = counter

    def uninterrupted(first, last):
        if first < 0 or last >= n or first > last or chains[first] != chains[last]:
            return False
        return bool(np.all(np.diff(internal[first:last + 1]) == 1))

    hydrogen = nitrogen.copy()
    for i in range(1, n):
        if kinds[i] == _PROLINE:
            continue
        direction = carbon[i - 1] - oxygen[i - 1]
        length = float(np.linalg.norm(direction))
        if length <= 0:
            raise ValueError("degenerate preceding C-O bond")
        hydrogen[i] += direction / length

    acceptor_index = np.full((n, 2), -1, dtype=np.int64)
    donor_index = np.full((n, 2), -1, dtype=np.int64)
    acceptor_energy = np.zeros((n, 2), dtype=float)
    donor_energy = np.zeros((n, 2), dtype=float)

    def record(partners, energies, owner, partner, energy):
        if energy < energies[owner, 0]:
            partners[owner, 1] = partners[owner, 0]
            energies[owner, 1] = energies[owner, 0]
            partners[owner, 0] = partner
            energies[owner, 0] = energy
        elif energy < energies[owner, 1]:
            partners[owner, 1] = partner
            energies[owner, 1] = energy

    def calculate_bond(donor, acceptor):
        energy = 0.0
        if kinds[donor] != _PROLINE:
            ho = _distance(hydrogen[donor], oxygen[acceptor])
            hc = _distance(hydrogen[donor], carbon[acceptor])
            nc = _distance(nitrogen[donor], carbon[acceptor])
            no = _distance(nitrogen[donor], oxygen[acceptor])
            if min(ho, hc, nc, no) < 0.5:
                energy = _MIN_ENERGY
            else:
                energy = (_COUPLING / ho - _COUPLING / hc
                          + _COUPLING / nc - _COUPLING / no)
                energy = max(_MIN_ENERGY, _round_milli(energy))
        record(acceptor_index, acceptor_energy, donor, acceptor, energy)
        record(donor_index, donor_energy, acceptor, donor, energy)

    nearby = []
    for i in range(n - 1):
        for j in range(i + 1, n):
            if _distance(alpha_carbon[i], alpha_carbon[j]) <= _MAX_CA_DISTANCE:
                nearby.append((i, j))
                calculate_bond(i, j)
                if j != i + 1:
                    calculate_bond(j, i)

    def has_bond(donor, acceptor):
        return any(acceptor_index[donor, rank] == acceptor
                   and acceptor_energy[donor, rank] < _BOND_THRESHOLD
                   for rank in (0, 1))

    def bridge_kind(i, j):
        if i == 0 or i + 1 >= n or j == 0 or j + 1 >= n:
            return None
        if not uninterrupted(i - 1, i + 1) or not uninterrupted(j - 1, j + 1):
            return None
        if ((has_bond(i + 1, j) and has_bond(j, i - 1))
                or (has_bond(j + 1, i) and has_bond(i, j - 1))):
            return "parallel"
        if ((has_bond(i + 1, j - 1) and has_bond(j + 1, i - 1))
                or (has_bond(j, i) and has_bond(i, j))):
            return "antiparallel"
        return None

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
                item["i"].append(i)
                item["j"].append(j)
                attached = True
                break
            if kind == "antiparallel" and j == item["j"][0] - 1:
                item["i"].append(i)
                item["j"].insert(0, j)
                attached = True
                break
        if not attached:
            bridges.append({"kind": kind, "i": [i], "j": [j]})

    bridges.sort(key=lambda item: (int(chains[item["i"][0]]), item["i"][0]))
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
                    or ibj < iei or ibj - iei >= 6
                    or (iei >= ibj and ibi <= iej))
            bulge = False
            if not skip and left["kind"] == "parallel":
                if jbj >= jei:
                    bulge = ((jbj - jei < 6 and ibj - iei < 3)
                             or jbj - jei < 3)
            elif not skip and jbi >= jej:
                bulge = ((jbi - jej < 6 and ibj - iei < 3)
                         or jbi - jej < 3)
            if bulge:
                left["i"].extend(right["i"])
                if left["kind"] == "parallel":
                    left["j"].extend(right["j"])
                else:
                    left["j"] = right["j"] + left["j"]
                bridges.pop(b)
            else:
                b += 1
        a += 1

    codes = np.full(n, "C", dtype="<U1")
    for item in bridges:
        code = "E" if len(item["i"]) > 1 else "B"
        for start, end in ((item["i"][0], item["i"][-1]),
                           (item["j"][0], item["j"][-1])):
            for i in range(start, end + 1):
                if codes[i] != "E":
                    codes[i] = code

    # flag values: none, start, end, start-and-end, middle
    flags = np.zeros((3, n), dtype=np.int8)
    for helix, stride in enumerate((3, 4, 5)):
        for i in range(n - stride):
            if uninterrupted(i, i + stride) and has_bond(i + stride, i):
                flags[helix, i + stride] = 2
                for middle in range(i + 1, i + stride):
                    if flags[helix, middle] == 0:
                        flags[helix, middle] = 4
                flags[helix, i] = 3 if flags[helix, i] == 2 else 1

    bend = np.zeros(n, dtype=bool)
    for i in range(2, n - 2):
        if (uninterrupted(i - 2, i + 2)
                and sequence_numbers[i - 2] + 4 == sequence_numbers[i + 2]):
            first = alpha_carbon[i] - alpha_carbon[i - 2]
            second = alpha_carbon[i + 2] - alpha_carbon[i]
            denominator = float(np.linalg.norm(first) * np.linalg.norm(second))
            if denominator > 0:
                cosine = float(np.clip(np.dot(first, second) / denominator, -1, 1))
                bend[i] = math.degrees(math.acos(cosine)) > 70.0

    is_start = lambda value: value in (1, 3)
    for i in range(1, n - 4):
        if is_start(flags[1, i]) and is_start(flags[1, i - 1]):
            codes[i:i + 4] = "H"
    for i in range(1, n - 3):
        if is_start(flags[0, i]) and is_start(flags[0, i - 1]):
            if all(code in {"C", "G"} for code in codes[i:i + 3]):
                codes[i:i + 3] = "G"
    for i in range(1, n - 5):
        if is_start(flags[2, i]) and is_start(flags[2, i - 1]):
            if all(code in {"C", "I", "H"} for code in codes[i:i + 5]):
                codes[i:i + 5] = "I"
    for i in range(1, n - 1):
        if codes[i] != "C":
            continue
        turn = False
        for helix, stride in enumerate((3, 4, 5)):
            for offset in range(1, stride):
                if i >= offset and is_start(flags[helix, i - offset]):
                    turn = True
                    break
            if turn:
                break
        if turn:
            codes[i] = "T"
        elif bend[i]:
            codes[i] = "S"

    return {
        "secondary_structure": codes.tolist(),
        "acceptor_index": acceptor_index,
        "acceptor_energy": acceptor_energy,
        "donor_index": donor_index,
        "donor_energy": donor_energy,
    }

