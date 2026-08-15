#!/usr/bin/env python3
"""Disclosed and hidden APBS LPBE problem descriptions."""

from __future__ import annotations


def atom(x, y, z, charge, radius=1.6):
    return [float(x), float(y), float(z), float(charge), float(radius)]


def case(name, atoms, *, lengths=(16.0, 16.0, 16.0), concentration=0.15,
         pdie=4.0, sdie=78.54, temperature=298.15):
    return {
        "name": name,
        "dims": [17, 17, 17],
        "lengths": list(lengths),
        "center": [0.0, 0.0, 0.0],
        "atoms": atoms,
        "concentration": float(concentration),
        "pdie": float(pdie),
        "sdie": float(sdie),
        "temperature": float(temperature),
        "ion_radius": 2.0,
        "surface": "smol",
        "solvent_radius": 1.4,
        "spline_window": 0.3,
    }


def public_cases():
    return [
        case("public_single_charge", [atom(0.2, -0.3, 0.1, 0.8, 1.55)]),
        case("public_dipole", [atom(-1.8, 0.0, 0.0, 0.55), atom(1.8, 0.0, 0.0, -0.55)],
             concentration=0.10),
        case("public_anisotropic_triad", [atom(-1.4, 0.7, -0.8, 0.6),
             atom(1.1, -0.9, 0.5, -0.4, 1.45), atom(0.4, 1.5, 1.2, -0.2, 1.7)],
             lengths=(16.0, 18.0, 20.0), pdie=6.0),
        case("public_single_dielectric", [atom(-1.0, -0.5, 0.6, 0.45),
             atom(1.2, 0.7, -0.4, -0.30), atom(0.2, -1.6, 0.3, -0.15)],
             pdie=40.0, sdie=40.0, concentration=0.05, temperature=310.0),
        case("public_smooth_cluster", [atom(-1.2, -0.8, -0.4, 0.45, 1.4),
             atom(1.0, -0.5, 0.7, -0.35, 1.65), atom(-0.3, 1.3, -0.6, 0.30, 1.5),
             atom(0.8, 1.0, 1.1, -0.25, 1.75)], pdie=2.0, concentration=0.20),
    ]


def hidden_cases():
    return [
        case("hidden_off_grid_monopole", [atom(-0.37, 0.42, -0.19, -0.7, 1.5)], pdie=3.0),
        case("hidden_zero_salt", [atom(-1.5, 0.2, 0.0, 0.5), atom(1.3, -0.3, 0.4, -0.5)],
             concentration=0.0),
        case("hidden_warm_solvent", [atom(-0.8, -1.2, 0.5, 0.35), atom(1.4, 0.9, -0.7, -0.25)],
             concentration=0.08, temperature=323.0, pdie=5.0),
        case("hidden_cold_solvent", [atom(0.3, -0.4, 0.8, 0.6, 1.8), atom(-1.7, 1.1, -0.5, -0.2)],
             concentration=0.18, temperature=278.0, pdie=8.0),
        case("hidden_rectangular_x", [atom(-2.0, 0.5, 0.2, 0.4), atom(1.5, -0.8, -0.9, -0.3)],
             lengths=(20.0, 16.0, 18.0), concentration=0.12),
        case("hidden_rectangular_y", [atom(-0.7, -2.1, 0.6, -0.45), atom(0.9, 1.8, -0.4, 0.35)],
             lengths=(18.0, 22.0, 16.0), pdie=7.0, concentration=0.22),
        case("hidden_rectangular_z", [atom(-0.9, 0.4, -2.2, 0.3), atom(1.2, -0.6, 1.7, -0.25)],
             lengths=(16.0, 18.0, 22.0), pdie=3.5, concentration=0.07),
        case("hidden_three_positive", [atom(-1.8, 0.0, 0.0, 0.22), atom(0.0, 1.5, 0.0, 0.18),
             atom(1.5, -0.8, 0.7, 0.20)], pdie=9.0, concentration=0.25),
        case("hidden_four_neutral", [atom(-1.5, -1.0, 0.5, 0.3), atom(1.4, -0.9, -0.4, -0.3),
             atom(-0.6, 1.4, -0.7, -0.2), atom(0.8, 1.2, 0.9, 0.2)], concentration=0.04),
        case("hidden_five_mixed", [atom(-1.8, -1.2, -0.6, 0.25, 1.4),
             atom(1.7, -1.0, 0.5, -0.20, 1.5), atom(-1.0, 1.5, 0.8, 0.18, 1.7),
             atom(1.1, 1.3, -0.9, -0.16, 1.55), atom(0.1, 0.0, 1.4, -0.07, 1.8)],
             pdie=2.5, concentration=0.16),
        case("hidden_high_dielectric", [atom(-1.1, 0.6, 0.4, 0.5), atom(1.3, -0.7, -0.5, -0.4)],
             pdie=20.0, concentration=0.11),
        case("hidden_uniform_water", [atom(-1.2, 0.8, -0.3, 0.4), atom(1.0, -0.6, 0.7, -0.25)],
             pdie=78.54, sdie=78.54, concentration=0.15),
        case("hidden_uniform_low", [atom(-0.9, -0.9, 0.2, 0.25), atom(0.9, 0.9, -0.2, -0.25)],
             pdie=12.0, sdie=12.0, concentration=0.03),
        case("hidden_net_negative", [atom(-1.4, 0.4, 0.8, -0.35), atom(0.5, -1.3, -0.6, 0.15),
             atom(1.2, 1.0, 0.3, -0.25)], pdie=6.0, concentration=0.19),
        case("hidden_compact_six", [atom(-1.0, -0.8, -0.6, 0.16, 1.35),
             atom(1.0, -0.7, -0.5, -0.14, 1.45), atom(-0.8, 0.9, -0.4, 0.12, 1.55),
             atom(0.9, 0.8, -0.3, -0.10, 1.65), atom(-0.3, 0.0, 1.0, 0.08, 1.5),
             atom(0.4, 0.1, 1.2, -0.06, 1.7)], pdie=3.0, concentration=0.13),
    ]
