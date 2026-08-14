#!/usr/bin/env python3
"""Locked real-Z2Pack reference for a fixed Hamiltonian mesh."""

from __future__ import annotations

import json
import logging
import math
import sys
from pathlib import Path

import numpy as np
import z2pack


def _load(path: Path) -> tuple[dict, np.ndarray]:
    case = json.loads(path.read_text())
    if case.get("schema") != "wannier90-z2-mesh-v1":
        raise ValueError("unsupported schema")
    if case.get("num_orbitals") != 4 or case.get("num_occupied") != 2:
        raise ValueError("only 4 orbitals and 2 occupied bands are supported")
    nlines = case.get("num_lines")
    nk = case.get("loop_points")
    tol = case.get("gap_tolerance")
    if not isinstance(nlines, int) or nlines < 3:
        raise ValueError("num_lines must be at least 3")
    if not isinstance(nk, int) or nk < 6:
        raise ValueError("loop_points must be at least 6")
    if not isinstance(tol, (float, int)) or not math.isfinite(tol) or tol <= 0:
        raise ValueError("gap_tolerance must be finite and positive")
    raw = np.asarray(case.get("hamiltonians"), dtype=float)
    if raw.shape != (nlines, nk, 4, 4, 2):
        raise ValueError(f"invalid Hamiltonian mesh shape {raw.shape}")
    mesh = raw[..., 0] + 1.0j * raw[..., 1]
    if not np.isfinite(mesh).all():
        raise ValueError("Hamiltonian mesh contains non-finite values")
    hermitian_error = float(np.max(np.abs(mesh - mesh.swapaxes(-1, -2).conjugate())))
    if hermitian_error > 1e-10:
        raise ValueError(f"Hamiltonian mesh is not Hermitian: {hermitian_error}")
    return case, mesh


def run_reference(path: Path) -> dict:
    case, mesh = _load(path)
    nlines, nk = case["num_lines"], case["loop_points"]
    eigvals = np.linalg.eigvalsh(mesh)
    min_gap = float(np.min(eigvals[..., 2] - eigvals[..., 1]))
    if min_gap <= case["gap_tolerance"]:
        return {
            "status": "gap_closed",
            "min_direct_gap": min_gap,
            "gap_tolerance": float(case["gap_tolerance"]),
        }

    def hamiltonian(k):
        kx = float(k[0]) % 1.0
        line = int(round(2.0 * kx * (nlines - 1)))
        loop = int(round((float(k[1]) % 1.0) * nk)) % nk
        if not 0 <= line < nlines:
            raise ValueError(f"surface point outside locked mesh: {k}")
        return mesh[line, loop]

    system = z2pack.hm.System(
        hamiltonian, dim=2, bands=2, convention=2, check_periodic=True
    )
    logging.getLogger("z2pack").setLevel(logging.ERROR)
    result = z2pack.surface.run(
        system=system,
        surface=lambda s, t: [s / 2.0, t],
        pos_tol=None,
        gap_tol=None,
        move_tol=None,
        num_lines=nlines,
        iterator=[nk + 1],
    )
    return {
        "status": "ok",
        "z2": int(z2pack.invariant.z2(result)),
        "min_direct_gap": min_gap,
        "line_positions": [float(x) for x in result.t],
        "wcc": [[float(x) for x in row] for row in result.wcc],
        "largest_gap_path": [float(x) for x in result.gap_pos],
        "largest_gap_size": [float(x) for x in result.gap_size],
        "num_lines": nlines,
        "loop_points": nk,
        "converged": True,
    }


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: reference_runner.py CASE.json", file=sys.stderr)
        return 2
    try:
        print(json.dumps(run_reference(Path(sys.argv[1])), sort_keys=True))
    except Exception as exc:  # The grader treats malformed input as rejection.
        print(json.dumps({"status": "invalid_input", "error": str(exc)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
