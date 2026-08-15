"""Clean-room uniform-grid LPBE finite-volume solver for PDB2PQR."""

from __future__ import annotations

import math

import numpy as np


SCHEMA = "algobridge-pdb2pqr-lpbe-grid-v1"
KB_SI = 1.3806581e-23
NA = 6.0221367e23


def _array(packet, name, dims, *, positive=False, unit_interval=False):
    values = np.asarray(packet.get(name), dtype=np.float64)
    if values.ndim != 1 or values.size != math.prod(dims):
        raise ValueError(f"{name} must be a flat grid array")
    if not np.all(np.isfinite(values)):
        raise ValueError(f"{name} contains a non-finite value")
    if positive and np.any(values <= 0.0):
        raise ValueError(f"{name} must be strictly positive")
    if unit_interval and (np.any(values < 0.0) or np.any(values > 1.0)):
        raise ValueError(f"{name} must lie in [0, 1]")
    return values.reshape(tuple(dims))


def _validate(packet):
    if not isinstance(packet, dict) or packet.get("schema") != SCHEMA:
        raise ValueError("unsupported packet schema")
    dims = packet.get("dims")
    if (not isinstance(dims, list) or len(dims) != 3 or
            any(type(value) is not int or value < 5 or value > 65 or value % 2 == 0 for value in dims)):
        raise ValueError("dims must contain three odd integers in [5, 65]")
    spacing = packet.get("spacing")
    if (not isinstance(spacing, list) or len(spacing) != 3 or
            any(not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0 for value in spacing)):
        raise ValueError("spacing must contain three positive finite values")
    for name in ("temperature", "zmagic"):
        value = packet.get(name)
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f"{name} must be positive and finite")
    zkappa2 = packet.get("zkappa2")
    if not isinstance(zkappa2, (int, float)) or not math.isfinite(zkappa2) or zkappa2 < 0:
        raise ValueError("zkappa2 must be nonnegative and finite")
    tolerance = packet.get("relative_tolerance")
    if not isinstance(tolerance, (int, float)) or not 1.0e-14 <= tolerance <= 1.0e-4:
        raise ValueError("relative_tolerance is outside the supported range")
    iterations = packet.get("max_iterations")
    if type(iterations) is not int or not 1 <= iterations <= 20000:
        raise ValueError("max_iterations is outside the supported range")
    arrays = {
        "diel_x": _array(packet, "diel_x", dims, positive=True),
        "diel_y": _array(packet, "diel_y", dims, positive=True),
        "diel_z": _array(packet, "diel_z", dims, positive=True),
        "kappa": _array(packet, "kappa", dims, unit_interval=True),
        "charge": _array(packet, "charge", dims),
        "boundary": _array(packet, "boundary", dims),
    }
    return dims, [float(value) for value in spacing], arrays


def solve_lpbe(packet):
    """Solve a mapped APBS-style LPBE problem with Jacobi-preconditioned CG."""
    dims, spacing, arrays = _validate(packet)
    nx, ny, nz = dims
    hx, hy, hz = spacing
    ex, ey, ez = arrays["diel_x"], arrays["diel_y"], arrays["diel_z"]
    kappa, charge, boundary = arrays["kappa"], arrays["charge"], arrays["boundary"]

    x_area = hy * hz / hx
    y_area = hx * hz / hy
    z_area = hx * hy / hz
    volume = hx * hy * hz
    cxp = ex[1:-1, 1:-1, 1:-1] * x_area
    cxm = ex[:-2, 1:-1, 1:-1] * x_area
    cyp = ey[1:-1, 1:-1, 1:-1] * y_area
    cym = ey[1:-1, :-2, 1:-1] * y_area
    czp = ez[1:-1, 1:-1, 1:-1] * z_area
    czm = ez[1:-1, 1:-1, :-2] * z_area
    diagonal = cxp + cxm + cyp + cym + czp + czm
    diagonal = diagonal + float(packet["zkappa2"]) * kappa[1:-1, 1:-1, 1:-1] * volume

    rhs = charge[1:-1, 1:-1, 1:-1] * float(packet["zmagic"]) * volume
    rhs = rhs.copy()
    rhs[0, :, :] += cxm[0, :, :] * boundary[0, 1:-1, 1:-1]
    rhs[-1, :, :] += cxp[-1, :, :] * boundary[-1, 1:-1, 1:-1]
    rhs[:, 0, :] += cym[:, 0, :] * boundary[1:-1, 0, 1:-1]
    rhs[:, -1, :] += cyp[:, -1, :] * boundary[1:-1, -1, 1:-1]
    rhs[:, :, 0] += czm[:, :, 0] * boundary[1:-1, 1:-1, 0]
    rhs[:, :, -1] += czp[:, :, -1] * boundary[1:-1, 1:-1, -1]

    def apply(values):
        result = diagonal * values
        result[:-1, :, :] -= cxp[:-1, :, :] * values[1:, :, :]
        result[1:, :, :] -= cxm[1:, :, :] * values[:-1, :, :]
        result[:, :-1, :] -= cyp[:, :-1, :] * values[:, 1:, :]
        result[:, 1:, :] -= cym[:, 1:, :] * values[:, :-1, :]
        result[:, :, :-1] -= czp[:, :, :-1] * values[:, :, 1:]
        result[:, :, 1:] -= czm[:, :, 1:] * values[:, :, :-1]
        return result

    solution = np.zeros((nx - 2, ny - 2, nz - 2), dtype=np.float64)
    residual = rhs.copy()
    rhs_norm = float(np.linalg.norm(rhs.ravel()))
    scale = max(rhs_norm, np.finfo(np.float64).tiny)
    relative = float(np.linalg.norm(residual.ravel())) / scale
    history = [relative]
    converged = relative <= float(packet["relative_tolerance"])
    iterations = 0
    if not converged:
        preconditioned = residual / diagonal
        direction = preconditioned.copy()
        rho = float(np.vdot(residual, preconditioned))
        for iterations in range(1, int(packet["max_iterations"]) + 1):
            product = apply(direction)
            denominator = float(np.vdot(direction, product))
            if not math.isfinite(denominator) or denominator <= 0.0:
                raise ArithmeticError("PCG lost positive definiteness")
            alpha = rho / denominator
            solution += alpha * direction
            residual -= alpha * product
            relative = float(np.linalg.norm(residual.ravel())) / scale
            history.append(relative)
            if relative <= float(packet["relative_tolerance"]):
                converged = True
                break
            preconditioned = residual / diagonal
            next_rho = float(np.vdot(residual, preconditioned))
            direction = preconditioned + (next_rho / rho) * direction
            rho = next_rho

    if not converged:
        raise ArithmeticError("PCG failed to converge")
    potential = boundary.copy()
    potential[1:-1, 1:-1, 1:-1] = solution
    thermal = KB_SI * float(packet["temperature"]) * 1.0e-3 * NA
    energy = 0.5 * float(np.sum(charge * potential)) * volume * thermal
    final_residual = rhs - apply(solution)
    absolute = float(np.linalg.norm(final_residual.ravel()))
    relative = absolute / scale
    return {
        "schema": "algobridge-pdb2pqr-lpbe-result-v1",
        "dims": dims,
        "potential": potential.ravel().tolist(),
        "energy_kj_mol": energy,
        "diagnostics": {
            "converged": True,
            "iterations": iterations,
            "absolute_residual": absolute,
            "relative_residual": relative,
            "residual_history": history,
        },
    }
