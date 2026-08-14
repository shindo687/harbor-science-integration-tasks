#!/usr/bin/env python3
"""Run unchanged locked BoltzTraP2 transport entry points."""

from __future__ import annotations

from fractions import Fraction
import json
import math
import os
from pathlib import Path
import sys

import numpy as np


DONOR = Path(os.environ.get("BTP_DONOR_ROOT", "/opt/reference-boltztrap2"))
sys.path.insert(0, str(DONOR))
from BoltzTraP2 import bandlib, units  # noqa: E402


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


def validate(payload):
    if payload.get("schema_version") != 1:
        raise ValueError("schema_version must be 1")
    units_contract = payload.get("units")
    if units_contract != {
        "energy": "eV", "velocity": "m/s", "volume": "angstrom^3"
    }:
        raise ValueError("unsupported units")
    energies = np.asarray(payload.get("band_energies_ev"), dtype=float)
    velocities = np.asarray(payload.get("velocities_m_per_s"), dtype=float)
    weights = np.asarray(payload.get("k_weights"), dtype=float)
    mus = np.asarray(payload.get("chemical_potentials_ev"), dtype=float)
    temperatures = np.asarray(payload.get("temperatures_k"), dtype=float)
    erange = np.asarray(payload.get("energy_range_ev"), dtype=float)
    if energies.ndim != 2 or not (1 <= energies.shape[0] <= 8):
        raise ValueError("band_energies_ev must have shape [1..8, nk]")
    nband, nk = energies.shape
    if not (1 <= nk <= 128):
        raise ValueError("nk must be in 1..128")
    if velocities.shape != (nband, nk, 3):
        raise ValueError("velocities_m_per_s shape mismatch")
    if weights.shape != (nk,):
        raise ValueError("k_weights shape mismatch")
    if mus.ndim != 1 or not (1 <= mus.size <= 9):
        raise ValueError("chemical_potentials_ev must contain 1..9 values")
    if temperatures.ndim != 1 or not (1 <= temperatures.size <= 6):
        raise ValueError("temperatures_k must contain 1..6 values")
    if erange.shape != (2,) or not erange[0] < erange[1]:
        raise ValueError("energy_range_ev must be increasing")
    arrays = [energies, velocities, weights, mus, temperatures, erange]
    if not all(np.all(np.isfinite(value)) for value in arrays):
        raise ValueError("all arrays must be finite")
    if np.any(weights <= 0.0) or abs(float(weights.sum()) - 1.0) > 1e-12:
        raise ValueError("k_weights must be positive and sum to one")
    if np.any(temperatures <= 0.0):
        raise ValueError("temperatures must be positive")
    if energies.min() < erange[0] or energies.max() > erange[1]:
        raise ValueError("band energies must lie inside energy_range_ev")
    volume = _finite_number(payload.get("volume_angstrom3"), "volume_angstrom3")
    spin = _finite_number(payload.get("spin_degeneracy"), "spin_degeneracy")
    reference = _finite_number(payload.get("reference_electrons"), "reference_electrons")
    bins = payload.get("energy_bins")
    if volume <= 0.0:
        raise ValueError("volume_angstrom3 must be positive")
    if spin <= 0.0:
        raise ValueError("spin_degeneracy must be positive")
    if reference < 0.0:
        raise ValueError("reference_electrons must be nonnegative")
    if isinstance(bins, bool) or not isinstance(bins, int) or not (32 <= bins <= 512):
        raise ValueError("energy_bins must be an integer in 32..512")
    return energies, velocities, weights, mus, temperatures, erange, volume, spin, reference, bins


def _multiplicities(weights):
    fractions = [Fraction(float(value)).limit_denominator(512) for value in weights]
    if any(abs(float(frac) - float(value)) > 1e-12 for frac, value in zip(fractions, weights)):
        raise ValueError("k_weights must be bounded rational mesh multiplicities")
    denominator = 1
    for frac in fractions:
        denominator = math.lcm(denominator, frac.denominator)
    multiplicities = [frac.numerator * (denominator // frac.denominator) for frac in fractions]
    common = math.gcd(*multiplicities)
    multiplicities = [value // common for value in multiplicities]
    if sum(multiplicities) > 1024:
        raise ValueError("expanded uniform k mesh exceeds 1024 points")
    return np.asarray(multiplicities, dtype=int)


def calculate(payload):
    (
        energies, velocities, weights, mus, temperatures, erange,
        volume, spin, reference, bins,
    ) = validate(payload)
    multiplicities = _multiplicities(weights)

    eband = energies * units.eV
    velocity_au = velocities * (units.Meter / units.Second)
    vvband = np.einsum("bki,bkj->bijk", velocity_au, velocity_au)
    eband = np.repeat(eband, multiplicities, axis=1)
    vvband = np.repeat(vvband, multiplicities, axis=3)

    epsilon, dos, sigma, _ = bandlib.BTPDOS(
        eband,
        vvband,
        erange=tuple(erange * units.eV),
        npts=bins,
        scattering_model="uniform_tau",
    )
    signed_n, l0, l1, l2, _ = bandlib.fermiintegrals(
        epsilon,
        dos,
        sigma,
        mus * units.eV,
        temperatures,
        dosweight=spin,
    )
    sigma_tau, seebeck, kappa_tau, _ = bandlib.calc_Onsager_coefficients(
        l0,
        l1,
        l2,
        mus * units.eV,
        temperatures,
        volume * units.Angstrom**3,
    )
    electron_count = -signed_n
    carrier_density = (electron_count - reference) / (volume * 1e-24)
    return {
        "schema_version": 1,
        "name": payload.get("name", "unnamed"),
        "electron_count": electron_count.tolist(),
        "carrier_density_cm3": carrier_density.tolist(),
        "L0": l0.tolist(),
        "L1": l1.tolist(),
        "L2": l2.tolist(),
        "sigma_over_tau_S_m_s": sigma_tau.tolist(),
        "seebeck_V_K": seebeck.tolist(),
        "kappa_over_tau_W_m_K_s": kappa_tau.tolist(),
    }


def main():
    payload = json.load(sys.stdin)
    json.dump(calculate(payload), sys.stdout, separators=(",", ":"), allow_nan=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

