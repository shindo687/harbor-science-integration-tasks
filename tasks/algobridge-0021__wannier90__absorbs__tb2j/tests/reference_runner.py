#!/usr/bin/env python3
"""Locked real-TB2J reference for bounded collinear Wannier H(R) data."""

from __future__ import annotations

import contextlib
import io
import json
import math
from pathlib import Path
import sys

import numpy as np
from ase import Atoms

from TB2J.exchangeCL2 import ExchangeCL2
from TB2J.myTB import MyTB


SCHEMA = "wannier90-tb2j-exchange-v1"


def _complex_matrix(case: dict, key: str, *, hermitian: bool) -> np.ndarray:
    raw = np.asarray(case.get(key), dtype=float)
    if raw.shape != (2, 2, 2):
        raise ValueError(f"{key} must have shape 2x2x2")
    matrix = raw[..., 0] + 1.0j * raw[..., 1]
    if not np.isfinite(matrix).all():
        raise ValueError(f"{key} contains non-finite values")
    if float(np.max(np.abs(matrix))) > 10.0:
        raise ValueError(f"{key} exceeds the bounded 10 eV magnitude")
    if hermitian and float(np.max(np.abs(matrix - matrix.conj().T))) > 1.0e-11:
        raise ValueError(f"{key} is not Hermitian")
    return matrix


def load_case(path: Path) -> tuple[dict, tuple[np.ndarray, ...]]:
    case = json.loads(path.read_text())
    if case.get("schema") != SCHEMA:
        raise ValueError("unsupported schema")
    if case.get("num_sites") != 2 or case.get("num_orbitals") != 2:
        raise ValueError("only two sites and two orbitals are supported")
    nk = case.get("kmesh")
    nz = case.get("contour_points")
    if not isinstance(nk, int) or nk < 5 or nk > 13 or nk % 2 != 1:
        raise ValueError("kmesh must be an odd integer from 5 through 13")
    if not isinstance(nz, int) or nz < 32 or nz > 128:
        raise ValueError("contour_points must be an integer from 32 through 128")
    efermi = case.get("fermi_energy")
    smearing = case.get("smearing")
    if (not isinstance(efermi, (int, float)) or not math.isfinite(efermi)
            or abs(float(efermi)) > 5.0):
        raise ValueError("fermi_energy must be finite and bounded by 5 eV")
    if (not isinstance(smearing, (int, float)) or not math.isfinite(smearing)
            or not 0.005 <= float(smearing) <= 0.2):
        raise ValueError("smearing must be finite and between 0.005 and 0.2 eV")
    matrices = (
        _complex_matrix(case, "h0_up", hermitian=True),
        _complex_matrix(case, "h1_up", hermitian=False),
        _complex_matrix(case, "h0_down", hermitian=True),
        _complex_matrix(case, "h1_down", hermitian=False),
    )
    return case, matrices


def _model(h0: np.ndarray, h1: np.ndarray, positions: np.ndarray,
           atoms: Atoms) -> MyTB:
    # MyTB stores the R=0 Hermitian matrix in half form and reconstructs H + H†.
    model = MyTB(
        nbasis=2,
        data={(0, 0, 0): h0 / 2.0, (1, 0, 0): h1},
        positions=positions,
    )
    model.set_atoms(atoms)
    return model


def run_reference(path: Path) -> dict:
    case, (h0_up, h1_up, h0_down, h1_down) = load_case(path)
    if (np.max(np.abs(h0_up - h0_down)) < 1.0e-12
            and np.max(np.abs(h1_up - h1_down)) < 1.0e-12):
        return {"status": "spin_degenerate"}

    atoms = Atoms(
        "Fe2",
        scaled_positions=[[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]],
        cell=np.diag([4.0, 10.0, 10.0]),
        pbc=True,
    )
    positions = np.asarray([[0.0, 0.0, 0.0], [0.5, 0.0, 0.0]])
    up = _model(h0_up, h1_up, positions, atoms)
    down = _model(h0_down, h1_down, positions, atoms)

    sink = io.StringIO()
    exchange = None
    with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
        exchange = ExchangeCL2(
            (up, down),
            atoms,
            efermi=float(case["fermi_energy"]),
            smearing=float(case["smearing"]),
            basis=["Fe1|d", "Fe2|d"],
            magnetic_elements=["Fe"],
            kmesh=[int(case["kmesh"]), 1, 1],
            emin=-20.0,
            emax=0.0,
            nz=int(case["contour_points"]),
            Rcut=None,
            nproc=1,
            integration_method="legendre",
            use_cache=False,
        )
        exchange.calculate_all()

    r_values = [int(r[0]) for r in exchange.short_Rlist]
    matrices = []
    for r in r_values:
        matrix = []
        for i in range(2):
            row = []
            for j in range(2):
                row.append(float(exchange.exchange_Jdict.get(((r, 0, 0), i, j), 0.0)))
            matrix.append(row)
        matrices.append(matrix)

    reversal_error = 0.0
    for ir, r in enumerate(r_values):
        jr = r_values.index(-r)
        for i in range(2):
            for j in range(2):
                reversal_error = max(
                    reversal_error,
                    abs(matrices[ir][i][j] - matrices[jr][j][i]),
                )

    moments = [float(value) for value in exchange.spinat[:, 2]]
    if min(abs(value) for value in moments) <= 1.0e-8:
        return {"status": "spin_degenerate", "moments_z": moments}
    result = {
        "status": "ok",
        "kmesh": int(case["kmesh"]),
        "contour_points": int(case["contour_points"]),
        "integration_emin": float(exchange.emin),
        "r_values": r_values,
        "moments_z": moments,
        "exchange_ev": matrices,
        "pair_reversal_max_error": float(reversal_error),
    }
    exchange.finalize()
    return result


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: reference_runner.py CASE.json", file=sys.stderr)
        return 2
    try:
        result = run_reference(Path(sys.argv[1]))
    except Exception as exc:
        result = {"status": "invalid_input", "error": str(exc)}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
