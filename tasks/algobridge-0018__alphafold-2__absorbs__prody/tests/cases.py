"""Deterministic hidden protein structures for elastic-network verification."""

from __future__ import annotations

import math


RESIDUES = ("ALA", "GLY", "SER", "LEU", "VAL", "THR")


def curve(n, shift=(0.0, 0.0, 0.0)):
    sx, sy, sz = shift
    return [
        [3.6 * i + sx, 1.8 * math.sin(0.8 * i) + sy,
         1.3 * math.cos(0.55 * i) + sz]
        for i in range(n)
    ]


def helix(n, shift=(0.0, 0.0, 0.0)):
    sx, sy, sz = shift
    return [
        [4.0 * math.cos(1.15 * i) + sx, 4.0 * math.sin(1.15 * i) + sy,
         1.7 * i + sz]
        for i in range(n)
    ]


def rotate(coords):
    # A fixed proper rotation, followed by translation, computed explicitly.
    ax, ay, az = 0.37, -0.51, 0.29
    cx, sx = math.cos(ax), math.sin(ax)
    cy, sy = math.cos(ay), math.sin(ay)
    cz, sz = math.cos(az), math.sin(az)
    rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))

    def multiply(a, b):
        return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3))
                           for j in range(3)) for i in range(3))

    matrix = multiply(rz, multiply(ry, rx))
    return [[sum(matrix[i][j] * xyz[j] for j in range(3)) + (11, -7, 4)[i]
             for i in range(3)] for xyz in coords]


def pdb_text(coords, *, chains=None, residue_numbers=None, plddt=None,
             missing_ca=()):
    n = len(coords)
    chains = list(chains or ("A" for _ in range(n)))
    residue_numbers = list(residue_numbers or range(1, n + 1))
    plddt = list(plddt or (90.0 for _ in range(n)))
    missing_ca = set(missing_ca)
    lines = ["MODEL        1"]
    serial = 1
    previous_chain = chains[0]
    for index, (xyz, chain, resnum, confidence) in enumerate(
            zip(coords, chains, residue_numbers, plddt)):
        if chain != previous_chain:
            lines.append(f"TER   {serial:5d}      {RESIDUES[(index-1) % len(RESIDUES)]:>3} {previous_chain}{residue_numbers[index-1]:4d}")
            serial += 1
            previous_chain = chain
        x, y, z = xyz
        atoms = [
            ("N", x - 1.20, y + 0.15, z - 0.10, "N"),
            ("CA", x, y, z, "C"),
            ("C", x + 1.20, y - 0.12, z + 0.08, "C"),
        ]
        for atom, px, py, pz, element in atoms:
            if atom == "CA" and index in missing_ca:
                continue
            name = atom if len(atom) == 4 else f" {atom}"
            lines.append(
                f"ATOM  {serial:5d} {name:<4} {RESIDUES[index % len(RESIDUES)]:>3} "
                f"{chain:1}{resnum:4d}    {px:8.3f}{py:8.3f}{pz:8.3f}"
                f"{1.00:6.2f}{confidence:6.2f}          {element:>2}  "
            )
            serial += 1
    lines.append(
        f"TER   {serial:5d}      {RESIDUES[(n-1) % len(RESIDUES)]:>3} "
        f"{chains[-1]}{residue_numbers[-1]:4d}"
    )
    lines.extend(("ENDMDL", "END"))
    return "\n".join(lines) + "\n"


def case(name, coords, **kwargs):
    pdb_options = kwargs.pop("pdb_options", {})
    return {
        "name": name,
        "format": kwargs.pop("format", "pdb"),
        "structure": pdb_text(coords, **pdb_options),
        "arguments": kwargs,
    }


def hidden_cases():
    base_curve = curve(9)
    base_helix = helix(10)
    tetrahedron = [
        [0.0, 0.0, 0.0], [5.0, 0.0, 0.0],
        [2.5, 4.330127, 0.0], [2.5, 1.443376, 4.082483],
    ]
    octahedron = [
        [4.0, 0.0, 0.0], [-4.0, 0.0, 0.0],
        [0.0, 4.0, 0.0], [0.0, -4.0, 0.0],
        [0.0, 0.0, 4.0], [0.0, 0.0, -4.0],
    ]
    disconnected_gnm = curve(5) + [
        [x + 35.0, y + 2.0, z - 1.0] for x, y, z in tetrahedron
    ]
    second_domain = [
        [38.0, 0.0, 0.0], [43.2, 0.3, 0.0],
        [40.7, 4.7, 0.4], [40.1, 1.5, 4.6], [44.1, 3.0, 3.3],
    ]
    disconnected_anm = tetrahedron + second_domain
    plddt = [95, 62, 88, 41, 77, 91, 69, 83, 55, 98]
    chains = ["A"] * 5 + ["B"] * 5
    residue_numbers = [1, 2, 4, 5, 8, 11, 12, 15, 16, 20]

    return [
        case("gnm_curved_chain", base_curve, model="gnm", cutoff=7.0,
             gamma=1.0, n_modes=5),
        case("anm_helix", base_helix, model="anm", cutoff=15.0,
             gamma=1.0, n_modes=6),
        case("gnm_plddt_selection", curve(10), model="gnm", cutoff=8.0,
             gamma=1.0, plddt_threshold=70.0, n_modes=4,
             pdb_options={"plddt": plddt}),
        case("anm_second_chain", helix(10), model="anm", chain_indices=[1],
             cutoff=15.0, gamma=1.0, n_modes=5,
             pdb_options={"chains": chains, "residue_numbers": residue_numbers}),
        case("gnm_missing_calpha", curve(9), model="gnm", cutoff=8.0,
             gamma=1.0, n_modes=4, pdb_options={"missing_ca": [3]}),
        case("gnm_disconnected_domains", disconnected_gnm, model="gnm",
             cutoff=7.0, gamma=1.0, n_modes=4),
        case("anm_disconnected_domains", disconnected_anm, model="anm",
             cutoff=7.5, gamma=1.0, n_modes=6),
        case("gnm_gamma_scaled", curve(8), model="gnm", cutoff=7.0,
             gamma=2.75, n_modes=4),
        case("anm_gamma_scaled", helix(9), model="anm", cutoff=15.0,
             gamma=0.45, n_modes=5),
        case("gnm_degenerate_tetrahedron", tetrahedron, model="gnm",
             cutoff=6.0, gamma=1.0, n_modes=3),
        case("anm_degenerate_octahedron", octahedron, model="anm",
             cutoff=6.0, gamma=1.0, n_modes=12),
        case("gnm_translated", [[x + 13.0, y - 8.0, z + 4.5]
                                for x, y, z in base_curve], model="gnm",
             cutoff=7.0, gamma=1.0, n_modes=5),
        case("anm_rotated", rotate(base_helix), model="anm", cutoff=15.0,
             gamma=1.0, n_modes=6),
        case("gnm_mmcif_multichain", curve(10), format="mmcif", model="gnm",
             chain_indices=[0, 1], cutoff=7.0, gamma=1.25, n_modes=5,
             pdb_options={"chains": chains, "residue_numbers": residue_numbers}),
        case("anm_residue_gaps", helix(9), model="anm", cutoff=15.0,
             gamma=1.2, plddt_threshold=60.0, n_modes=5,
             pdb_options={"residue_numbers": [2, 3, 7, 8, 9, 14, 18, 19, 25],
                          "plddt": [92, 81, 73, 64, 58, 96, 88, 77, 69]}),
    ]
