#!/usr/bin/env python3
"""Unprivileged adapter for the submitted native LAMMPS pair style."""

from __future__ import annotations

import os
from pathlib import Path
import pwd
import subprocess
import tempfile

from cases import validate_case


LAMMPS = Path(os.environ.get("CANDIDATE_LAMMPS", "/testbed/src/lmp_serial"))
POTENTIAL = Path(os.environ.get("MTP_CANDIDATE_POTENTIAL", "/opt/candidate-assets/mtp9-bounded.mtp"))
PRESSURE_CONVERSION = 1602176.6208
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001


def _write_data(path, packet, atom_types=1):
    lx, ly, lz = packet["box"]
    lines = [
        "LAMMPS bounded MTP case", "", f"{len(packet['positions'])} atoms",
        f"{atom_types} atom types", "", f"0.0 {lx:.16e} xlo xhi",
        f"0.0 {ly:.16e} ylo yhi", f"0.0 {lz:.16e} zlo zhi", "", "Masses", "",
    ]
    for atom_type in range(1, atom_types + 1):
        lines.append(f"{atom_type} 1.0")
    lines.extend(["", "Atoms # atomic", ""])
    for index, point in enumerate(packet["positions"], 1):
        atom_type = 2 if atom_types == 2 and index == len(packet["positions"]) else 1
        lines.append(
            f"{index} {atom_type} {point[0]:.16e} {point[1]:.16e} {point[2]:.16e}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _write_input(path, data, dump, *, cutoff=5.0, potential=POTENTIAL):
    path.write_text("\n".join([
        "units metal", "atom_style atomic", "boundary p p p", f"read_data {data}",
        f"pair_style mtp_bounded {cutoff:.16g}", f"pair_coeff * * {potential}",
        "neighbor 0.2 bin", "neigh_modify every 1 delay 0 check yes", "thermo 1",
        "thermo_style custom step pe pxx pyy pzz pyz pxz pxy vol",
        "thermo_modify format float %.17g", f"dump result all custom 1 {dump} id fx fy fz",
        "dump_modify result sort id format line \"%d %.17g %.17g %.17g\"", "run 0",
    ]) + "\n", encoding="ascii")


def _candidate_command(input_path):
    if os.environ.get("CANDIDATE_RUN_AS_USER") == "0":
        return [str(LAMMPS), "-in", str(input_path), "-log", "none"]
    return [
        "runuser", "-u", "candidate", "--", str(LAMMPS),
        "-in", str(input_path), "-log", "none",
    ]


def _parse_screen(stdout):
    lines = stdout.splitlines()
    header = next(index for index, line in enumerate(lines)
                  if line.split() == ["Step", "PotEng", "Pxx", "Pyy", "Pzz",
                                      "Pyz", "Pxz", "Pxy", "Volume"])
    fields = lines[header + 1].split()
    if len(fields) != 9 or int(fields[0]) != 0:
        raise RuntimeError("LAMMPS emitted a malformed thermo row")
    return [float(value) for value in fields[1:]]


def _parse_dump(path, count):
    lines = path.read_text(encoding="utf-8").splitlines()
    marker = next(index for index, line in enumerate(lines) if line.startswith("ITEM: ATOMS"))
    rows = []
    for line in lines[marker + 1:marker + 1 + count]:
        fields = line.split()
        rows.append((int(fields[0]), [float(fields[1]), float(fields[2]), float(fields[3])]))
    rows.sort()
    if [identifier for identifier, _ in rows] != list(range(1, count + 1)):
        raise RuntimeError("LAMMPS force dump has invalid atom identifiers")
    return [force for _, force in rows]


def run_candidate(packet):
    validate_case(packet)
    with tempfile.TemporaryDirectory(prefix="mtp-candidate-") as temp_name:
        directory = Path(temp_name)
        if os.environ.get("CANDIDATE_RUN_AS_USER") != "0":
            os.chown(directory, CANDIDATE_UID, CANDIDATE_GID)
        data, input_path, dump = directory / "case.data", directory / "case.in", directory / "force.dump"
        _write_data(data, packet)
        _write_input(input_path, data, dump)
        for path in (data, input_path):
            path.chmod(0o644)
        completed = subprocess.run(
            _candidate_command(input_path), text=True, capture_output=True,
            timeout=30, check=False,
        )
        if completed.returncode:
            raise RuntimeError(
                f"candidate LAMMPS failed ({completed.returncode}): "
                f"{completed.stderr[-1000:]}{completed.stdout[-1200:]}"
            )
        energy, pxx, pyy, pzz, pyz, pxz, pxy, volume = _parse_screen(completed.stdout)
        virial = [value * volume / PRESSURE_CONVERSION
                  for value in (pxx, pyy, pzz, pyz, pxz, pxy)]
        return {
            "energy": energy,
            "forces": _parse_dump(dump, len(packet["positions"])),
            "virial": virial,
        }


def run_invalid(packet, mode):
    validate_case(packet)
    with tempfile.TemporaryDirectory(prefix="mtp-invalid-") as temp_name:
        directory = Path(temp_name)
        if os.environ.get("CANDIDATE_RUN_AS_USER") != "0":
            os.chown(directory, CANDIDATE_UID, CANDIDATE_GID)
        data, input_path, dump = directory / "case.data", directory / "case.in", directory / "force.dump"
        atom_types = 2 if mode == "two_types" else 1
        _write_data(data, packet, atom_types=atom_types)
        cutoff = 4.75 if mode == "cutoff_mismatch" else 5.0
        malformed = Path(os.environ.get(
            "MTP_MALFORMED_POTENTIAL", "/opt/candidate-assets/malformed.mtp"
        ))
        potential = malformed if mode == "malformed" else POTENTIAL
        if mode == "missing":
            potential = directory / "does-not-exist.mtp"
        _write_input(input_path, data, dump, cutoff=cutoff, potential=potential)
        for path in (data, input_path):
            path.chmod(0o644)
        completed = subprocess.run(
            _candidate_command(input_path), text=True, capture_output=True,
            timeout=20, check=False,
        )
        return completed.returncode != 0
