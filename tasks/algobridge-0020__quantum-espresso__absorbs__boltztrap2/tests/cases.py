"""Deterministic public and hidden fixtures for ALGOBRIDGE-0020."""

from __future__ import annotations

import copy
import math
import random


BASE_Q = [
    (-0.92, -0.31, 0.18),
    (-0.71, 0.44, -0.63),
    (-0.38, -0.82, 0.57),
    (-0.14, 0.73, 0.86),
    (0.11, -0.57, -0.77),
    (0.33, 0.88, -0.24),
    (0.62, -0.46, 0.69),
    (0.87, 0.27, -0.49),
]


def _weights(multiplicities):
    total = float(sum(multiplicities))
    return [value / total for value in multiplicities]


def _case(
    name,
    band_specs,
    *,
    qpoints=BASE_Q,
    multiplicities=None,
    mus=(-0.18, 0.0, 0.18),
    temperatures=(150.0, 300.0, 700.0),
    volume=160.0,
    spin=2.0,
    reference_electrons=None,
    energy_range=(-1.2, 1.2),
    bins=192,
):
    """Create analytic QE-style bands with Cartesian group velocities.

    Each band specification is ``(offset, (ax, ay, az), velocity_scale)`` and
    uses E(q) = offset + ax*qx^2 + ay*qy^2 + az*qz^2.  The velocity vectors
    are deterministic derivatives scaled into realistic m/s magnitudes.
    """
    energies = []
    velocities = []
    for offset, axes, velocity_scale in band_specs:
        eband = []
        vband = []
        for qx, qy, qz in qpoints:
            eband.append(
                offset + axes[0] * qx * qx + axes[1] * qy * qy
                + axes[2] * qz * qz
            )
            vband.append(
                [
                    velocity_scale * axes[0] * qx,
                    velocity_scale * axes[1] * qy,
                    velocity_scale * axes[2] * qz,
                ]
            )
        energies.append(eband)
        velocities.append(vband)
    if multiplicities is None:
        multiplicities = [1] * len(qpoints)
    if reference_electrons is None:
        reference_electrons = spin * len(band_specs) / 2.0
    return {
        "schema_version": 1,
        "name": name,
        "units": {
            "energy": "eV",
            "velocity": "m/s",
            "volume": "angstrom^3",
        },
        "band_energies_ev": energies,
        "velocities_m_per_s": velocities,
        "k_weights": _weights(multiplicities),
        "volume_angstrom3": float(volume),
        "chemical_potentials_ev": list(mus),
        "temperatures_k": list(temperatures),
        "spin_degeneracy": float(spin),
        "reference_electrons": float(reference_electrons),
        "energy_range_ev": list(energy_range),
        "energy_bins": int(bins),
    }


def _particle_hole(name, *, temperatures=(100.0, 300.0, 900.0), bins=224):
    qpoints = BASE_Q + [(0.51, 0.52, 0.53), (-0.51, -0.52, -0.53)]
    positive = []
    negative = []
    vpositive = []
    vnegative = []
    for qx, qy, qz in qpoints:
        e = 0.085 + 0.16 * qx * qx + 0.11 * qy * qy + 0.07 * qz * qz
        v = [2.5e5 * qx, 1.7e5 * qy, 1.1e5 * qz]
        positive.append(e)
        negative.append(-e)
        vpositive.append(v)
        vnegative.append([-value for value in v])
    return {
        "schema_version": 1,
        "name": name,
        "units": {
            "energy": "eV",
            "velocity": "m/s",
            "volume": "angstrom^3",
        },
        "band_energies_ev": [negative, positive],
        "velocities_m_per_s": [vnegative, vpositive],
        "k_weights": _weights([1] * len(qpoints)),
        "volume_angstrom3": 128.0,
        "chemical_potentials_ev": [-0.15, 0.0, 0.15],
        "temperatures_k": list(temperatures),
        "spin_degeneracy": 2.0,
        "reference_electrons": 2.0,
        "energy_range_ev": [-0.65, 0.65],
        "energy_bins": bins,
    }


def public_cases():
    return [
        _case(
            "public_isotropic_two_band",
            [(-0.42, (0.12, 0.12, 0.12), 3.2e5),
             (0.08, (0.18, 0.18, 0.18), 3.2e5)],
        ),
        _particle_hole("public_particle_hole"),
        _case(
            "public_anisotropic_offdiagonal",
            [(-0.31, (0.07, 0.21, 0.43), 4.1e5),
             (0.04, (0.51, 0.13, 0.09), 2.8e5)],
            mus=(-0.25, -0.05, 0.12, 0.28),
            temperatures=(75.0, 350.0),
            volume=92.0,
        ),
        _case(
            "public_symmetry_weights",
            [(-0.27, (0.14, 0.23, 0.08), 3.7e5),
             (0.16, (0.31, 0.06, 0.19), 2.3e5)],
            multiplicities=(1, 2, 3, 4, 4, 3, 2, 1),
            temperatures=(200.0, 600.0),
        ),
        _case(
            "public_rank_one_transport",
            [(0.02, (0.24, 0.0, 0.0), 4.0e5)],
            mus=(-0.1, 0.1, 0.3),
            temperatures=(120.0, 500.0),
            reference_electrons=0.5,
            energy_range=(-0.5, 0.7),
            bins=160,
        ),
    ]


def hidden_cases():
    rng = random.Random(20260815)
    random_q = [
        tuple(rng.uniform(-0.95, 0.95) for _ in range(3))
        for _ in range(19)
    ]
    cases = [
        _case(
            "hidden_low_temperature",
            [(-0.18, (0.09, 0.15, 0.22), 3.5e5),
             (0.025, (0.27, 0.11, 0.19), 3.0e5)],
            mus=(-0.04, 0.0, 0.04), temperatures=(12.0, 35.0), bins=384,
        ),
        _case(
            "hidden_high_temperature",
            [(-0.6, (0.2, 0.1, 0.3), 2.2e5),
             (0.25, (0.4, 0.2, 0.1), 3.2e5)],
            mus=(-0.7, 0.0, 0.7), temperatures=(800.0, 1600.0, 2400.0),
            energy_range=(-1.4, 1.4),
        ),
        _case(
            "hidden_spin_one",
            [(-0.22, (0.13, 0.17, 0.21), 3.3e5),
             (0.12, (0.19, 0.07, 0.29), 2.6e5)],
            spin=1.0, reference_electrons=1.0,
        ),
        _case(
            "hidden_empty_fermi_window",
            [(0.65, (0.08, 0.08, 0.08), 2.1e5)],
            mus=(-0.85, -0.7), temperatures=(20.0, 80.0),
            reference_electrons=0.0, energy_range=(-1.0, 1.0), bins=256,
        ),
        _case(
            "hidden_three_bands",
            [(-0.58, (0.05, 0.09, 0.14), 2.0e5),
             (-0.11, (0.22, 0.08, 0.17), 3.8e5),
             (0.33, (0.12, 0.31, 0.06), 2.9e5)],
            mus=(-0.5, -0.2, 0.1, 0.4), reference_electrons=3.0,
        ),
        _case(
            "hidden_high_multiplicity_weights",
            [(-0.25, (0.16, 0.12, 0.25), 3.1e5),
             (0.09, (0.28, 0.18, 0.07), 2.7e5)],
            multiplicities=(1, 7, 2, 11, 5, 3, 13, 6),
        ),
        _case(
            "hidden_flat_band_zero_velocity",
            [(-0.15, (0.0, 0.0, 0.0), 0.0),
             (0.06, (0.25, 0.19, 0.11), 3.2e5)],
            reference_electrons=2.0,
        ),
        _case(
            "hidden_nearly_rank_two",
            [(0.01, (0.24, 0.18, 1.0e-8), 3.6e5)],
            reference_electrons=0.7, energy_range=(-0.6, 0.8), bins=224,
        ),
        _case(
            "hidden_dense_mu_temperature_grid",
            [(-0.4, (0.11, 0.16, 0.09), 2.4e5),
             (0.05, (0.2, 0.14, 0.28), 3.4e5)],
            mus=(-0.45, -0.3, -0.15, 0.0, 0.15, 0.3, 0.45),
            temperatures=(60.0, 180.0, 420.0, 900.0), bins=320,
        ),
        _case(
            "hidden_random_mesh",
            [(-0.3, (0.15, 0.08, 0.21), 3.3e5),
             (0.14, (0.27, 0.19, 0.1), 2.8e5)],
            qpoints=random_q,
            multiplicities=tuple(1 + (i * 7) % 5 for i in range(len(random_q))),
            bins=288,
        ),
        _particle_hole(
            "hidden_particle_hole_cold_hot",
            temperatures=(25.0, 250.0, 1250.0), bins=320,
        ),
        _case(
            "hidden_small_volume",
            [(-0.2, (0.12, 0.18, 0.27), 3.5e5),
             (0.2, (0.31, 0.09, 0.16), 2.2e5)],
            volume=18.5,
        ),
        _case(
            "hidden_large_volume",
            [(-0.2, (0.12, 0.18, 0.27), 3.5e5),
             (0.2, (0.31, 0.09, 0.16), 2.2e5)],
            volume=2400.0,
        ),
        _case(
            "hidden_single_kpoint",
            [(-0.42, (0.50, 0.01, 0.01), 3.0e5),
             (-0.13, (0.01, 0.50, 0.01), 3.0e5),
             (0.16, (0.01, 0.01, 0.50), 3.0e5),
             (0.48, (0.25, 0.25, 0.25), 3.0e5)],
            qpoints=((0.4, -0.2, 0.7),), multiplicities=(1,),
            mus=(-0.1, 0.03, 0.2), temperatures=(100.0, 500.0),
            reference_electrons=4.0, energy_range=(-0.8, 1.1), bins=192,
        ),
        _case(
            "hidden_four_band_stress",
            [(-0.72, (0.04, 0.08, 0.12), 1.8e5),
             (-0.28, (0.17, 0.11, 0.06), 2.6e5),
             (0.07, (0.23, 0.09, 0.19), 3.2e5),
             (0.41, (0.12, 0.29, 0.15), 2.4e5)],
            qpoints=random_q[:13],
            multiplicities=(1, 2, 1, 3, 2, 4, 1, 2, 3, 1, 2, 1, 3),
            mus=(-0.65, -0.3, 0.0, 0.3, 0.65),
            temperatures=(90.0, 300.0, 1000.0),
            reference_electrons=4.0, energy_range=(-1.4, 1.4), bins=352,
        ),
    ]
    return cases


def transformed_pairs():
    """Metamorphic cases: energy shift and input-order permutations."""
    base = hidden_cases()[9]

    shifted = copy.deepcopy(base)
    shifted["name"] = "metamorphic_common_energy_shift"
    shift = 0.37
    shifted["band_energies_ev"] = [
        [value + shift for value in band] for band in base["band_energies_ev"]
    ]
    shifted["chemical_potentials_ev"] = [
        value + shift for value in base["chemical_potentials_ev"]
    ]
    shifted["energy_range_ev"] = [
        value + shift for value in base["energy_range_ev"]
    ]

    permuted = copy.deepcopy(base)
    permuted["name"] = "metamorphic_band_k_permutation"
    band_order = list(reversed(range(len(base["band_energies_ev"]))))
    k_order = list(reversed(range(len(base["k_weights"]))))
    permuted["band_energies_ev"] = [
        [base["band_energies_ev"][b][k] for k in k_order]
        for b in band_order
    ]
    permuted["velocities_m_per_s"] = [
        [base["velocities_m_per_s"][b][k] for k in k_order]
        for b in band_order
    ]
    permuted["k_weights"] = [base["k_weights"][k] for k in k_order]
    return [(base, shifted), (base, permuted)]


def invalid_cases():
    valid = public_cases()[0]
    cases = []

    def changed(name, edit):
        item = copy.deepcopy(valid)
        item["name"] = name
        edit(item)
        cases.append(item)

    changed("invalid_weight_sum", lambda x: x.__setitem__("k_weights", [0.1] * 8))
    changed("invalid_negative_weight", lambda x: x["k_weights"].__setitem__(0, -0.1))
    changed("invalid_bad_velocity_shape", lambda x: x["velocities_m_per_s"][0][0].pop())
    changed("invalid_band_shape", lambda x: x["band_energies_ev"][0].pop())
    changed("invalid_zero_volume", lambda x: x.__setitem__("volume_angstrom3", 0.0))
    changed("invalid_zero_temperature", lambda x: x["temperatures_k"].__setitem__(0, 0.0))
    changed("invalid_nonfinite", lambda x: x["band_energies_ev"][0].__setitem__(0, math.nan))
    changed("invalid_bad_spin", lambda x: x.__setitem__("spin_degeneracy", -1.0))
    changed("invalid_too_few_bins", lambda x: x.__setitem__("energy_bins", 1))
    changed("invalid_reversed_energy_range", lambda x: x.__setitem__("energy_range_ev", [1.0, -1.0]))
    return cases
