#!/usr/bin/env python3
"""Private locked OpenMM -> locked pymbar reference runner."""

from __future__ import annotations

import json
import os
import sys

os.environ["PYMBAR_DISABLE_JAX"] = "1"

import numpy as np
from openmm import Context, CustomExternalForce, Platform, System, VerletIntegrator, Vec3
from openmm import unit
from pymbar import MBAR


def reduced_potentials(spec):
    positions = np.asarray(spec["positions"], dtype=float)
    rows = []
    for center, stiffness, offset in zip(
            spec["centers"], spec["stiffness"], spec["state_offsets"], strict=True):
        system = System()
        system.addParticle(1.0)
        force = CustomExternalForce("0.5*k*(x-x0)^2+offset")
        force.addGlobalParameter("k", float(stiffness))
        force.addGlobalParameter("x0", float(center))
        force.addGlobalParameter("offset", float(offset))
        force.addParticle(0, [])
        system.addForce(force)
        integrator = VerletIntegrator(0.001)
        context = Context(system, integrator, Platform.getPlatformByName("Reference"))
        energies = []
        for x in positions:
            context.setPositions([Vec3(float(x), 0.0, 0.0)] * unit.nanometer)
            value = context.getState(getEnergy=True).getPotentialEnergy()
            energies.append(value.value_in_unit(unit.kilojoule_per_mole))
        del context, integrator
        rows.append(energies)
    u_kn = np.asarray(rows, dtype=float)
    if spec.get("common_offset") == "alternating_extreme":
        n = u_kn.shape[1]
        shared = np.where(np.arange(n) % 2, -850.0, 900.0)
        shared += 0.125 * np.sin(np.arange(n))
        u_kn = u_kn + shared
    return u_kn


def solve(spec):
    u_kn = reduced_potentials(spec)
    n_k = np.asarray(spec["N_k"], dtype=int)
    kwargs = {
        "relative_tolerance": float(spec["relative_tolerance"]),
        "maximum_iterations": int(spec["maximum_iterations"]),
        "verbose": False,
    }
    if spec.get("initial_f_k") is not None:
        kwargs["initial_f_k"] = np.asarray(spec["initial_f_k"], dtype=float)
    estimator = MBAR(u_kn, n_k, **kwargs)
    differences = estimator.compute_free_energy_differences(return_theta=True)
    return {
        "input": {
            "name": spec["name"],
            "u_kn": u_kn.tolist(),
            "N_k": n_k.tolist(),
            "initial_f_k": spec.get("initial_f_k"),
            "relative_tolerance": spec["relative_tolerance"],
            "maximum_iterations": spec["maximum_iterations"],
        },
        "expected": {
            "f_k": np.asarray(estimator.f_k, dtype=float).tolist(),
            "Delta_f": np.asarray(differences["Delta_f"], dtype=float).tolist(),
            "dDelta_f": np.asarray(differences["dDelta_f"], dtype=float).tolist(),
            "covariance": np.asarray(differences["Theta"], dtype=float).tolist(),
            "weights": np.asarray(estimator.weights(), dtype=float).tolist(),
            "overlap": np.asarray(estimator.compute_overlap()["matrix"], dtype=float).tolist(),
            "effective_sample_number": np.asarray(
                estimator.compute_effective_sample_number(), dtype=float).tolist(),
        },
    }


def main():
    request = json.load(sys.stdin)
    response = {
        "openmm_version": Platform.getOpenMMVersion(),
        "cases": [solve(case) for case in request["cases"]],
    }
    json.dump(response, sys.stdout, allow_nan=False, separators=(",", ":"))


if __name__ == "__main__":
    main()

