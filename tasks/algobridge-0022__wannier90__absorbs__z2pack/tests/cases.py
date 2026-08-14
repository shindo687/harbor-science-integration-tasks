"""Deterministic Hamiltonian-mesh fixtures for the Wannier90/Z2Pack task."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import numpy as np


PAULI_X = np.array([[0.0, -1.0j], [1.0j, 0.0]], dtype=complex)
PAULI_Y = np.array([[0.0, 1.0], [1.0, 0.0]], dtype=complex)
PAULI_Z = np.diag([1.0, -1.0]).astype(complex)


def _bhz_hamiltonian(kx: float, ky: float, *, a: float, b: float,
                     c: float, d: float, mass: float) -> np.ndarray:
    """The lattice BHZ model used by Z2Pack's own Hamiltonian example."""
    x, y = 2.0 * np.pi * np.array([kx, ky])

    def block(px: float, py: float) -> np.ndarray:
        dx = a * np.sin(px)
        dy = -a * np.sin(py)
        dz = -2.0 * b * (2.0 - mass / (2.0 * b) - np.cos(px) - np.cos(py))
        eps = c - 2.0 * d * (2.0 - np.cos(px) - np.cos(py))
        return dx * PAULI_X + dy * PAULI_Y + dz * PAULI_Z + eps * np.eye(2)

    upper = block(x, y)
    lower = block(-x, -y).conjugate()
    return np.block([[upper, np.zeros((2, 2))], [np.zeros((2, 2)), lower]])


def _unitary(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    raw = rng.normal(size=(4, 4)) + 1.0j * rng.normal(size=(4, 4))
    q, r = np.linalg.qr(raw)
    phases = np.diag(r)
    phases = np.where(np.abs(phases) > 0.0, phases / np.abs(phases), 1.0)
    return q @ np.diag(phases.conjugate())


def make_case(name: str, *, mass: float, a: float = 0.5, b: float = 1.0,
              c: float = 0.0, d: float = 0.0, num_lines: int = 15,
              loop_points: int = 28, gap_tolerance: float = 1.0e-7,
              gauge_seed: int | None = None, energy_scale: float = 1.0) -> dict:
    if num_lines < 3 or loop_points < 6:
        raise ValueError("mesh is too small")
    gauge = np.eye(4, dtype=complex) if gauge_seed is None else _unitary(gauge_seed)
    mesh = []
    for line_index in range(num_lines):
        kx = 0.5 * line_index / (num_lines - 1)
        line = []
        for loop_index in range(loop_points):
            ky = loop_index / loop_points
            ham = energy_scale * _bhz_hamiltonian(
                kx, ky, a=a, b=b, c=c, d=d, mass=mass
            )
            ham = gauge.conjugate().T @ ham @ gauge
            line.append([[[float(z.real), float(z.imag)] for z in row] for row in ham])
        mesh.append(line)
    return {
        "schema": "wannier90-z2-mesh-v1",
        "name": name,
        "num_orbitals": 4,
        "num_occupied": 2,
        "num_lines": num_lines,
        "loop_points": loop_points,
        "gap_tolerance": gap_tolerance,
        "hamiltonians": mesh,
    }


PUBLIC_SPECS = [
    dict(name="public_topological_bhz", mass=1.0, num_lines=11, loop_points=20),
    dict(name="public_trivial_bhz", mass=-1.0, num_lines=11, loop_points=20),
    dict(name="public_topological_gauge", mass=3.0, gauge_seed=2203,
         num_lines=13, loop_points=24),
    dict(name="public_trivial_dispersive", mass=-2.0, c=0.3, d=0.12,
         num_lines=13, loop_points=24),
    dict(name="public_topological_scaled", mass=1.4, a=0.8, energy_scale=0.2,
         num_lines=15, loop_points=28),
]


HIDDEN_SPECS = [
    dict(name="hidden_topological_base", mass=0.6, num_lines=17, loop_points=30),
    dict(name="hidden_trivial_base", mass=-0.4, num_lines=17, loop_points=30),
    dict(name="hidden_topological_mass_2", mass=2.0, a=0.35, num_lines=19,
         loop_points=32),
    dict(name="hidden_trivial_mass_minus_3", mass=-3.0, a=0.9, num_lines=19,
         loop_points=32),
    dict(name="hidden_topological_random_basis_1", mass=1.0, gauge_seed=2211,
         num_lines=21, loop_points=34),
    dict(name="hidden_trivial_random_basis_1", mass=-1.0, gauge_seed=2212,
         num_lines=21, loop_points=34),
    dict(name="hidden_topological_random_basis_2", mass=3.2, gauge_seed=2213,
         num_lines=23, loop_points=36),
    dict(name="hidden_trivial_random_basis_2", mass=-1.7, gauge_seed=2214,
         num_lines=23, loop_points=36),
    dict(name="hidden_topological_particle_hole_asym", mass=1.2, c=0.15, d=0.08,
         num_lines=25, loop_points=38),
    dict(name="hidden_trivial_particle_hole_asym", mass=-0.8, c=-0.1, d=0.17,
         num_lines=25, loop_points=38),
    dict(name="hidden_topological_small_gap", mass=0.12, a=0.22,
         gap_tolerance=1e-8, num_lines=27, loop_points=42),
    dict(name="hidden_trivial_small_gap", mass=-0.12, a=0.22,
         gap_tolerance=1e-8, num_lines=27, loop_points=42),
    dict(name="hidden_topological_energy_scaled", mass=2.8, a=0.65,
         energy_scale=1e-2, gap_tolerance=1e-10, num_lines=29, loop_points=44),
    dict(name="hidden_trivial_energy_scaled", mass=-2.2, a=0.65,
         energy_scale=25.0, num_lines=29, loop_points=44),
    dict(name="hidden_topological_dense", mass=1.8, a=1.1, gauge_seed=2215,
         num_lines=31, loop_points=48),
]


def public_cases() -> list[dict]:
    return [make_case(**spec) for spec in PUBLIC_SPECS]


def hidden_cases() -> list[dict]:
    return [make_case(**spec) for spec in HIDDEN_SPECS]


def invalid_cases() -> list[tuple[str, dict]]:
    base = make_case("invalid_base", mass=1.0, num_lines=7, loop_points=12)
    result: list[tuple[str, dict]] = []

    item = copy.deepcopy(base); item["schema"] = "wrong-schema"
    result.append(("wrong_schema", item))
    item = copy.deepcopy(base); item["num_orbitals"] = 6
    result.append(("unsupported_orbitals", item))
    item = copy.deepcopy(base); item["num_occupied"] = 1
    result.append(("unsupported_occupied", item))
    item = copy.deepcopy(base); item["num_lines"] = 1
    result.append(("line_count_mismatch", item))
    item = copy.deepcopy(base); item["loop_points"] = 4
    result.append(("loop_count_mismatch", item))
    item = copy.deepcopy(base); item["gap_tolerance"] = -1.0
    result.append(("negative_gap_tolerance", item))
    item = copy.deepcopy(base); item["hamiltonians"][0][0][0][1][1] += 0.2
    result.append(("non_hermitian", item))
    item = copy.deepcopy(base); del item["hamiltonians"][0][-1]
    result.append(("ragged_mesh", item))
    item = make_case("gap_closing", mass=0.0, num_lines=9, loop_points=16,
                     gap_tolerance=1e-5)
    result.append(("gap_closing", item))
    item = copy.deepcopy(base); item["hamiltonians"][0][0][0][0][0] = float("nan")
    result.append(("non_finite", item))
    return result


def canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=True)


def case_digest(data: dict) -> str:
    return hashlib.sha256(canonical_json(data).encode()).hexdigest()


def write_case(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")

