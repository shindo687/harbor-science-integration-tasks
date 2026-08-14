#!/usr/bin/env python3
"""Deterministic public, hidden, invalid, and metamorphic exchange cases."""

from __future__ import annotations

from copy import deepcopy
import json
import math
from pathlib import Path


def _pair(value: complex) -> list[float]:
    value = complex(value)
    return [float(value.real), float(value.imag)]


def _matrix(values) -> list[list[list[float]]]:
    return [[_pair(values[i][j]) for j in range(2)] for i in range(2)]


def _h0(diagonal, offdiag) -> list[list[list[float]]]:
    return _matrix(
        [[complex(diagonal[0]), complex(offdiag)],
         [complex(offdiag).conjugate(), complex(diagonal[1])]]
    )


def make_case(
    name: str,
    *,
    up=(-0.82, -0.64),
    down=(0.78, 0.62),
    off_up=-0.48 + 0.00j,
    off_down=-0.44 + 0.00j,
    hop_up=((-0.14 + 0.00j, -0.11 + 0.02j),
            (0.01 - 0.01j, -0.09 + 0.00j)),
    hop_down=((-0.12 + 0.00j, -0.09 - 0.01j),
              (0.02 + 0.01j, -0.08 + 0.00j)),
    kmesh=9,
    contour_points=80,
    fermi_energy=0.0,
    smearing=0.04,
) -> dict:
    return {
        "name": name,
        "schema": "wannier90-tb2j-exchange-v1",
        "num_sites": 2,
        "num_orbitals": 2,
        "kmesh": int(kmesh),
        "contour_points": int(contour_points),
        "fermi_energy": float(fermi_energy),
        "smearing": float(smearing),
        "h0_up": _h0(up, off_up),
        "h1_up": _matrix(hop_up),
        "h0_down": _h0(down, off_down),
        "h1_down": _matrix(hop_down),
    }


def gauge_transform(case: dict, theta0: float, theta1: float, name: str) -> dict:
    result = deepcopy(case)
    result["name"] = name
    theta = [theta0, theta1]
    for key in ("h0_up", "h1_up", "h0_down", "h1_down"):
        for i in range(2):
            for j in range(2):
                raw = result[key][i][j]
                value = complex(float(raw[0]), float(raw[1]))
                value *= complex(math.cos(theta[j] - theta[i]),
                                 math.sin(theta[j] - theta[i]))
                result[key][i][j] = _pair(value)
    return result


def energy_shift(case: dict, shift: float, name: str) -> dict:
    result = deepcopy(case)
    result["name"] = name
    result["fermi_energy"] += shift
    for key in ("h0_up", "h0_down"):
        for i in range(2):
            result[key][i][i][0] += shift
    return result


def public_cases() -> list[dict]:
    base = make_case("public_ferromagnetic_chain")
    antiferro = make_case(
        "public_antiferromagnetic_chain",
        up=(-0.92, 0.70), down=(0.88, -0.68),
        off_up=-0.36, off_down=-0.34,
        hop_up=((-0.11, -0.08), (0.02, -0.07)),
        hop_down=((-0.10, -0.07), (0.01, -0.06)),
    )
    complex_case = make_case(
        "public_complex_hopping", off_up=-0.42 + 0.17j,
        off_down=-0.39 - 0.11j,
        hop_up=((-0.16 + 0.02j, -0.10 + 0.08j),
                (0.03 - 0.04j, -0.08 - 0.01j)),
        hop_down=((-0.13 - 0.02j, -0.07 - 0.05j),
                  (0.01 + 0.03j, -0.09 + 0.02j)),
    )
    coarse = make_case(
        "public_coarse_kmesh", up=(-1.05, -0.73), down=(0.93, 0.69),
        kmesh=7, contour_points=72, smearing=0.03,
    )
    shifted = energy_shift(gauge_transform(base, 0.37, -0.91,
                                            "public_shifted_gauge"),
                           0.63, "public_shifted_gauge")
    return [base, antiferro, complex_case, coarse, shifted]


def hidden_cases() -> list[dict]:
    return [
        make_case("hidden_reference_variant", up=(-0.76, -0.58),
                  down=(0.72, 0.67), off_up=-0.53, off_down=-0.49),
        make_case("hidden_antiferromagnetic", up=(-1.08, 0.61),
                  down=(1.01, -0.57), off_up=-0.31 + 0.04j,
                  off_down=-0.29 - 0.03j),
        make_case("hidden_weak_intercell", hop_up=((-0.03, -0.025),
                  (0.004, -0.02)), hop_down=((-0.028, -0.021),
                  (0.003, -0.018))),
        make_case("hidden_asymmetric_sites", up=(-1.20, -0.43),
                  down=(0.84, 0.51), off_up=-0.37, off_down=-0.52),
        make_case("hidden_complex_nonsymmetric_h1", off_up=-0.40 + 0.21j,
                  off_down=-0.35 - 0.16j,
                  hop_up=((-0.12 + 0.04j, -0.19 + 0.07j),
                          (0.06 - 0.11j, -0.05 + 0.02j)),
                  hop_down=((-0.09 - 0.03j, -0.14 - 0.08j),
                            (0.02 + 0.09j, -0.07 - 0.01j))),
        make_case("hidden_kmesh_5", kmesh=5, contour_points=68,
                  up=(-0.86, 0.59), down=(0.81, -0.55),
                  off_up=-0.33, off_down=-0.31),
        make_case("hidden_kmesh_7", kmesh=7, contour_points=76,
                  off_up=-0.57, off_down=-0.46),
        make_case("hidden_kmesh_11", kmesh=11, contour_points=84,
                  up=(-0.95, -0.52), down=(0.88, 0.57)),
        make_case("hidden_kmesh_13", kmesh=13, contour_points=88,
                  hop_up=((-0.18, -0.13), (0.04, -0.11))),
        make_case("hidden_contour_64", contour_points=64, smearing=0.025),
        make_case("hidden_contour_104", contour_points=104, smearing=0.055,
                  up=(-0.97, 0.66), down=(0.89, -0.61),
                  off_up=-0.39, off_down=-0.35),
        make_case("hidden_fermi_offset", fermi_energy=0.18,
                  up=(-0.73, -0.49), down=(0.91, 0.74)),
        make_case("hidden_small_smearing", smearing=0.012,
                  up=(-1.12, 0.74), down=(0.67, -0.69),
                  off_up=-0.28, off_down=-0.27),
        gauge_transform(make_case("hidden_gauge_base", kmesh=11),
                        -1.17, 0.83, "hidden_random_gauge"),
        energy_shift(make_case("hidden_shift_base", kmesh=7,
                               contour_points=92, smearing=0.065),
                     -0.77, "hidden_energy_shift"),
    ]


def invalid_cases() -> list[tuple[str, dict]]:
    base = make_case("invalid_base")
    rows: list[tuple[str, dict]] = []

    case = deepcopy(base); case["schema"] = "wrong"
    rows.append(("wrong_schema", case))
    case = deepcopy(base); case["num_sites"] = 3
    rows.append(("unsupported_sites", case))
    case = deepcopy(base); case["kmesh"] = 8
    rows.append(("even_kmesh", case))
    case = deepcopy(base); case["kmesh"] = 3
    rows.append(("small_kmesh", case))
    case = deepcopy(base); case["contour_points"] = 31
    rows.append(("small_contour", case))
    case = deepcopy(base); case["smearing"] = -0.01
    rows.append(("negative_smearing", case))
    case = deepcopy(base); case["h0_up"][0][1][0] += 0.25
    rows.append(("non_hermitian_h0", case))
    case = deepcopy(base); case["h1_down"] = case["h1_down"][:1]
    rows.append(("wrong_shape", case))
    case = deepcopy(base); case["h0_up"][0][0][0] = float("nan")
    rows.append(("non_finite", case))
    case = deepcopy(base); case["h0_down"] = deepcopy(case["h0_up"])
    case["h1_down"] = deepcopy(case["h1_up"])
    rows.append(("spin_degenerate", case))
    return rows


def metamorphic_pairs() -> list[tuple[str, dict, dict]]:
    gauge_base = make_case("meta_gauge_base", kmesh=11, contour_points=88)
    shift_base = make_case("meta_shift_base", kmesh=7, contour_points=92,
                           smearing=0.05)
    return [
        ("local_orbital_phase_gauge", gauge_base,
         gauge_transform(gauge_base, 0.71, -1.09, "meta_gauge_rotated")),
        ("common_energy_origin_shift", shift_base,
         energy_shift(shift_base, 0.91, "meta_energy_shifted")),
    ]


def write_case(path: Path, case: dict) -> None:
    path.write_text(json.dumps(case, indent=2, allow_nan=True) + "\n")
