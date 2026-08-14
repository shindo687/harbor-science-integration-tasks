#!/usr/bin/env python3
"""Run the locked pristine LAMMPS -> pristine phonopy reference path."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import random
import subprocess
import tempfile

import numpy as np
from phonopy import Phonopy
from phonopy.harmonic.force_constants import get_drift_force_constants
from phonopy.structure.atoms import PhonopyAtoms
from phonopy.units import VaspToTHz

from cases import CASE_BY_NAME


def _require_c_backend():
    try:
        import phonopy._phonopy  # noqa: F401  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError(f"locked phonopy C backend is unavailable: {exc!r}") from exc


def _vectors(case):
    d = float(case["delta"])
    result = []
    for axis in range(3):
        v = [0.0, 0.0, 0.0]
        v[axis] = d
        result.append(v)
        result.append([-x for x in v])
    if case["redundant"]:
        s = d / math.sqrt(3.0)
        result.extend(([s, s, s], [-s, -s, -s]))
    return result


def _write_data(path: Path, phonon: Phonopy):
    scell = phonon.supercell
    cell = np.asarray(scell.cell, dtype=float)
    if np.max(np.abs(cell - np.diag(np.diag(cell)))) > 1e-12:
        raise RuntimeError("reference fixtures require orthogonal cells")
    symbols = list(scell.symbols)
    masses = np.asarray(scell.masses, dtype=float)
    type_for_symbol = {}
    type_ids = []
    type_masses = {}
    for symbol, mass in zip(symbols, masses, strict=True):
        if symbol not in type_for_symbol:
            type_for_symbol[symbol] = len(type_for_symbol) + 1
            type_masses[type_for_symbol[symbol]] = float(mass)
        type_ids.append(type_for_symbol[symbol])
    positions = np.asarray(scell.positions, dtype=float)
    lines = [
        "ALGOBRIDGE-0024 pristine LAMMPS finite-displacement cell",
        "",
        f"{len(symbols)} atoms",
        f"{len(type_for_symbol)} atom types",
        "",
        f"0.0 {cell[0, 0]:.17g} xlo xhi",
        f"0.0 {cell[1, 1]:.17g} ylo yhi",
        f"0.0 {cell[2, 2]:.17g} zlo zhi",
        "",
        "Masses",
        "",
    ]
    for type_id in sorted(type_masses):
        lines.append(f"{type_id} {type_masses[type_id]:.17g}")
    lines.extend(("", "Atoms # atomic", ""))
    for idx, (type_id, xyz) in enumerate(zip(type_ids, positions, strict=True), 1):
        lines.append(
            f"{idx} {type_id} {xyz[0]:.17g} {xyz[1]:.17g} {xyz[2]:.17g}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_lammps_input(path: Path, data_path: Path, case, records, dump_dir: Path):
    lines = [
        "units metal",
        "atom_style atomic",
        "boundary p p p",
        f"read_data {data_path}",
        f"pair_style lj/cut {case['cutoff']:.17g}",
        f"pair_coeff * * {case['epsilon']:.17g} {case['sigma']:.17g} {case['cutoff']:.17g}",
        "pair_modify shift yes",
        "neighbor 0.25 bin",
        "neigh_modify delay 0 every 1 check yes",
        "run 0 post no",
        f"write_dump all custom {dump_dir / 'baseline.dump'} id fx fy fz modify sort id",
    ]
    current_atom = None
    for index, record in enumerate(records):
        atom = int(record["atom"])
        if atom != current_atom:
            if current_atom is not None:
                lines.append("group algobridge_disp delete")
            lines.append(f"group algobridge_disp id {atom + 1}")
            current_atom = atom
        dx, dy, dz = record["displacement"]
        lines.extend(
            (
                f"displace_atoms algobridge_disp move {dx:.17g} {dy:.17g} {dz:.17g} units box",
                "run 0 post no",
                f"write_dump all custom {dump_dir / f'record-{index:04d}.dump'} id fx fy fz modify sort id",
                f"displace_atoms algobridge_disp move {-dx:.17g} {-dy:.17g} {-dz:.17g} units box",
            )
        )
    if current_atom is not None:
        lines.append("group algobridge_disp delete")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_dump(path: Path, n_atoms: int):
    lines = path.read_text(encoding="utf-8").splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.startswith("ITEM: ATOMS")) + 1
    except StopIteration as exc:
        raise RuntimeError(f"invalid LAMMPS dump: {path}") from exc
    rows = []
    for line in lines[start : start + n_atoms]:
        fields = line.split()
        rows.append((int(fields[0]), [float(x) for x in fields[1:4]]))
    rows.sort(key=lambda item: item[0])
    if [item[0] for item in rows] != list(range(1, n_atoms + 1)):
        raise RuntimeError(f"non-canonical atom ids in {path}")
    return np.asarray([item[1] for item in rows], dtype=float)


def _phase_links(phonon: Phonopy):
    primitive = phonon.primitive
    p2s = np.asarray(primitive.p2s_map, dtype=int)
    s2p = np.asarray(primitive.s2p_map, dtype=int)
    svecs, multi = primitive.get_smallest_vectors()
    links = []
    for i in range(len(p2s)):
        row = []
        for j in range(len(p2s)):
            terms = []
            for k in range(len(phonon.supercell)):
                if int(s2p[k]) != int(p2s[j]):
                    continue
                count, address = (int(x) for x in multi[k, i])
                vectors = np.asarray(svecs[address : address + count], dtype=float)
                terms.append({"force_atom": k, "vectors": vectors.tolist()})
            row.append(terms)
        links.append(row)
    return links


def _diagnostics(fc, records):
    squared = 0.0
    count = 0
    for record in records:
        atom = int(record["atom"])
        u = np.asarray(record["displacement"], dtype=float)
        forces = np.asarray(record["forces"], dtype=float)
        predicted = -np.einsum("a,iab->ib", u, fc[atom])
        squared += float(np.sum((predicted - forces) ** 2))
        count += forces.size
    fit_rms = math.sqrt(squared / count)
    drift0, drift1, _, _ = get_drift_force_constants(fc, lang="C")
    permutation = float(np.max(np.abs(fc - fc.transpose(1, 0, 3, 2))))
    return fit_rms, max(abs(float(drift0)), abs(float(drift1))), permutation


def generate(case, lammps_executable: Path, work_dir: Path):
    _require_c_backend()
    unitcell = PhonopyAtoms(
        symbols=case["symbols"],
        masses=case["masses"],
        cell=case["cell"],
        scaled_positions=case["scaled_positions"],
    )
    phonon = Phonopy(
        unitcell,
        np.diag(case["supercell"]),
        primitive_matrix=np.eye(3),
        is_symmetry=False,
        log_level=0,
        lang="C",
    )
    n_atoms = len(phonon.supercell)
    records = [
        {"atom": atom, "displacement": vector}
        for atom in range(n_atoms)
        for vector in _vectors(case)
    ]
    data_path = work_dir / "cell.data"
    input_path = work_dir / "reference.in"
    dump_dir = work_dir / "dumps"
    dump_dir.mkdir(parents=True)
    _write_data(data_path, phonon)
    _write_lammps_input(input_path, data_path, case, records, dump_dir)
    proc = subprocess.run(
        [str(lammps_executable), "-log", "none", "-screen", "none", "-in", str(input_path)],
        cwd=work_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=180,
        check=False,
        env={"PATH": os.environ.get("PATH", "/usr/bin:/bin")},
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pristine LAMMPS failed ({proc.returncode}):\n{proc.stdout}")
    baseline = _read_dump(dump_dir / "baseline.dump", n_atoms)
    rng = np.random.default_rng(int(case["seed"]))
    for index, record in enumerate(records):
        force = _read_dump(dump_dir / f"record-{index:04d}.dump", n_atoms) - baseline
        if case["noise"]:
            noise = rng.normal(0.0, float(case["noise"]), size=force.shape)
            noise -= noise.mean(axis=0, keepdims=True)
            force += noise
        record["forces"] = force.tolist()
    if case["shuffle"]:
        random.Random(int(case["seed"])).shuffle(records)

    candidate_input = {
        "format": "algobridge-fc2-v1",
        "frequency_factor": float(VaspToTHz),
        "symmetrize_iterations": int(case["symmetrize_iterations"]),
        "supercell": {
            "n_atoms": n_atoms,
            "n_primitive": len(phonon.primitive),
            "cell": np.asarray(phonon.supercell.cell, dtype=float).tolist(),
            "scaled_positions": np.asarray(phonon.supercell.scaled_positions, dtype=float).tolist(),
            "symbols": list(phonon.supercell.symbols),
            "masses": np.asarray(phonon.primitive.masses, dtype=float).tolist(),
            "p2s_map": np.asarray(phonon.primitive.p2s_map, dtype=int).tolist(),
            "phase_links": _phase_links(phonon),
        },
        "records": records,
        "qpoints": case["qpoints"],
    }

    phonon.dataset = {
        "natom": n_atoms,
        "first_atoms": [
            {
                "number": int(record["atom"]),
                "displacement": np.asarray(record["displacement"], dtype=float),
                "forces": np.asarray(record["forces"], dtype=float),
            }
            for record in records
        ],
    }
    phonon.produce_force_constants(
        calculate_full_force_constants=True,
        fc_calculator="traditional",
        show_drift=False,
    )
    phonon.symmetrize_force_constants(
        level=int(case["symmetrize_iterations"]),
        show_drift=False,
        use_symfc_projector=False,
    )
    fc = np.asarray(phonon.force_constants, dtype=float)
    fit_rms, asr_max, permutation_max = _diagnostics(fc, records)
    qpoint_results = []
    for qpoint in case["qpoints"]:
        phonon.dynamical_matrix.run(qpoint)
        dm = np.asarray(phonon.dynamical_matrix.dynamical_matrix, dtype=complex)
        eigenvalues, eigenvectors = np.linalg.eigh(dm)
        frequencies = np.sign(eigenvalues) * np.sqrt(np.abs(eigenvalues)) * float(VaspToTHz)
        qpoint_results.append(
            {
                "qpoint": qpoint,
                "dynamical_matrix_real": dm.real.tolist(),
                "dynamical_matrix_imag": dm.imag.tolist(),
                "eigenvalues": eigenvalues.tolist(),
                "frequencies": frequencies.tolist(),
                "eigenvectors_real": eigenvectors.real.tolist(),
                "eigenvectors_imag": eigenvectors.imag.tolist(),
            }
        )
    reference = {
        "format": "algobridge-fc2-result-v1",
        "force_constants": fc.tolist(),
        "fit_residual_rms": fit_rms,
        "asr_max": asr_max,
        "permutation_max": permutation_max,
        "qpoint_results": qpoint_results,
    }
    return candidate_input, reference


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=sorted(CASE_BY_NAME))
    parser.add_argument("--lammps", required=True, type=Path)
    parser.add_argument("--input-out", required=True, type=Path)
    parser.add_argument("--reference-out", required=True, type=Path)
    parser.add_argument("--work-dir", type=Path)
    args = parser.parse_args()
    if args.work_dir is None:
        with tempfile.TemporaryDirectory(prefix="algobridge0024-ref-") as tmp:
            candidate_input, reference = generate(
                CASE_BY_NAME[args.case], args.lammps.resolve(), Path(tmp)
            )
    else:
        args.work_dir.mkdir(parents=True, exist_ok=True)
        candidate_input, reference = generate(
            CASE_BY_NAME[args.case], args.lammps.resolve(), args.work_dir.resolve()
        )
    args.input_out.write_text(json.dumps(candidate_input, indent=2) + "\n", encoding="utf-8")
    args.reference_out.write_text(json.dumps(reference, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
