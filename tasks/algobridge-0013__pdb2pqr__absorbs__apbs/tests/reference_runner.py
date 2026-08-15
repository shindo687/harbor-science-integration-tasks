#!/usr/bin/env python3
"""Root-only wrapper around the locked official APBS 3.4.1 release."""

from __future__ import annotations

import json
import math
import os
import re
import subprocess
import tempfile
from pathlib import Path


APBS = os.environ.get(
    "APBS_REFERENCE_EXECUTABLE",
    "/opt/reference-apbs/APBS-3.4.1.Linux/bin/apbs",
)
ENERGY = re.compile(r"Total electrostatic energy\s*=\s*([+\-0-9.Ee]+)\s+kJ/mol")
ITEMS = re.compile(r"items\s+(\d+)\s+data follows")


def pqr_text(atoms):
    rows = []
    for serial, (x, y, z, charge, radius) in enumerate(atoms, 1):
        rows.append(
            f"ATOM  {serial:5d}  C   MOL A   1    "
            f"{x:8.3f}{y:8.3f}{z:8.3f} {charge:7.4f} {radius:6.4f}"
        )
    return "\n".join(rows) + "\nEND\n"


def input_text(description):
    nx, ny, nz = description["dims"]
    lx, ly, lz = description["lengths"]
    cx, cy, cz = description["center"]
    concentration = description["concentration"]
    ions = ""
    if concentration > 0:
        radius = description["ion_radius"]
        ions = (
            f"    ion charge 1 conc {concentration:.12g} radius {radius:.12g}\n"
            f"    ion charge -1 conc {concentration:.12g} radius {radius:.12g}\n"
        )
    return f"""read
    mol pqr molecule.pqr
end

elec name bounded
    mg-manual
    dime {nx} {ny} {nz}
    glen {lx:.12g} {ly:.12g} {lz:.12g}
    gcent {cx:.12g} {cy:.12g} {cz:.12g}
    mol 1
    lpbe
    bcfl sdh
{ions}    pdie {description['pdie']:.12g}
    sdie {description['sdie']:.12g}
    chgm spl0
    srfm {description['surface']}
    srad {description['solvent_radius']:.12g}
    swin {description['spline_window']:.12g}
    sdens 10.0
    temp {description['temperature']:.12g}
    calcenergy total
    calcforce no
    write pot dx bounded-pot
    write dielx dx bounded-dielx
    write diely dx bounded-diely
    write dielz dx bounded-dielz
    write kappa dx bounded-kappa
    write charge dx bounded-charge
end

quit
"""


def read_dx(path):
    text = path.read_text(encoding="utf-8")
    match = ITEMS.search(text)
    if match is None:
        raise RuntimeError(f"invalid DX file: {path.name}")
    count = int(match.group(1))
    body = text.split("data follows", 1)[1].split("attribute", 1)[0]
    values = [float(item) for item in body.split()[:count]]
    if len(values) != count:
        raise RuntimeError(f"truncated DX file: {path.name}")
    return values


def constants(description):
    avogadro = 6.022045000e23
    electron_esu = 4.803242384e-10
    boltzmann_erg = 1.380662000e-16
    temperature = description["temperature"]
    zmagic = 4.0 * math.pi * electron_esu**2 / (boltzmann_erg * temperature) * 1.0e8
    ionic_strength = description["concentration"]
    zkappa2 = ionic_strength * 1.0e-16 * (
        8.0 * math.pi * avogadro * electron_esu**2
    ) / (1000.0 * boltzmann_erg * temperature)
    return zmagic, zkappa2


def run(description):
    with tempfile.TemporaryDirectory(prefix="apbs-lpbe-") as raw:
        directory = Path(raw)
        (directory / "molecule.pqr").write_text(pqr_text(description["atoms"]), encoding="utf-8")
        (directory / "problem.in").write_text(input_text(description), encoding="utf-8")
        completed = subprocess.run(
            [APBS, "problem.in"], cwd=directory, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"APBS failed ({completed.returncode}): {completed.stderr}\n{completed.stdout[-2000:]}"
            )
        energies = ENERGY.findall(completed.stdout)
        if len(energies) != 1:
            raise RuntimeError("APBS energy was not uniquely reported")
        potential = read_dx(directory / "bounded-pot.dx")
        diel_x = read_dx(directory / "bounded-dielx.dx")
        diel_y = read_dx(directory / "bounded-diely.dx")
        diel_z = read_dx(directory / "bounded-dielz.dx")
        kappa = read_dx(directory / "bounded-kappa.dx")
        charge = read_dx(directory / "bounded-charge.dx")

    dims = description["dims"]
    total = math.prod(dims)
    if any(len(values) != total for values in (potential, diel_x, diel_y, diel_z, kappa, charge)):
        raise RuntimeError("APBS map shape mismatch")
    boundary = [0.0] * total
    nx, ny, nz = dims
    for i in range(nx):
        for j in range(ny):
            for k in range(nz):
                if i in (0, nx - 1) or j in (0, ny - 1) or k in (0, nz - 1):
                    index = (i * ny + j) * nz + k
                    boundary[index] = potential[index]
    zmagic, zkappa2 = constants(description)
    spacing = [description["lengths"][axis] / (dims[axis] - 1) for axis in range(3)]
    packet = {
        "schema": "algobridge-pdb2pqr-lpbe-grid-v1",
        "dims": dims,
        "spacing": spacing,
        "temperature": description["temperature"],
        "zmagic": zmagic,
        "zkappa2": zkappa2,
        "diel_x": diel_x,
        "diel_y": diel_y,
        "diel_z": diel_z,
        "kappa": kappa,
        "charge": charge,
        "boundary": boundary,
        "relative_tolerance": 1.0e-10,
        "max_iterations": 5000,
    }
    return {
        "name": description["name"],
        "packet": packet,
        "expected": {
            "potential": potential,
            "energy_kj_mol": float(energies[0]),
        },
    }


def main():
    for line in __import__("sys").stdin:
        try:
            request = json.loads(line)
            result = run(request["description"])
            print(json.dumps({"ok": True, "result": result}, separators=(",", ":")), flush=True)
        except Exception as error:
            print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}), flush=True)


if __name__ == "__main__":
    main()
