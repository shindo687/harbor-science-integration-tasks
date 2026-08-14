#!/usr/bin/env python3
"""Compile and invoke the candidate's native QE Fortran transport module."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile


MODULE = Path("PP/src/transport_moments.f90")
TENSOR_KEYS = (
    "L0",
    "L1",
    "L2",
    "sigma_over_tau_S_m_s",
    "seebeck_V_K",
    "kappa_over_tau_W_m_K_s",
)


def _line(values):
    return " ".join(format(float(value), ".17g") for value in values)


def serialize(payload):
    energies = payload["band_energies_ev"]
    velocities = payload["velocities_m_per_s"]
    weights = payload["k_weights"]
    mus = payload["chemical_potentials_ev"]
    temperatures = payload["temperatures_k"]
    nband = len(energies)
    nk = len(energies[0])
    if any(len(band) != nk for band in energies):
        raise ValueError("ragged band_energies_ev")
    if len(velocities) != nband or any(len(band) != nk for band in velocities):
        raise ValueError("velocities shape mismatch")
    if any(len(vector) != 3 for band in velocities for vector in band):
        raise ValueError("velocity vector shape mismatch")
    if len(weights) != nk:
        raise ValueError("k_weights shape mismatch")
    erange = payload["energy_range_ev"]
    lines = [
        f"{nband} {nk} {len(mus)} {len(temperatures)} {int(payload['energy_bins'])}",
        _line([
            payload["volume_angstrom3"],
            payload["spin_degeneracy"],
            payload["reference_electrons"],
            erange[0],
            erange[1],
        ]),
        _line(weights),
        _line(mus),
        _line(temperatures),
    ]
    for iband in range(nband):
        for ik in range(nk):
            lines.append(_line([energies[iband][ik], *velocities[iband][ik]]))
    return "\n".join(lines) + "\n"


def _nested_matrix(values, nt, nmu):
    result = []
    position = 0
    for _ in range(nt):
        row = []
        for _ in range(nmu):
            matrix = []
            for _ in range(3):
                matrix.append(values[position:position + 3])
                position += 3
            row.append(matrix)
        result.append(row)
    return result, position


def parse_output(text, name):
    tokens = text.split()
    if len(tokens) < 4 or tokens[0] != "TMV1":
        raise RuntimeError("candidate emitted an invalid header")
    status, nt, nmu = map(int, tokens[1:4])
    if status != 0:
        raise RuntimeError(f"candidate rejected the input with status {status}")
    numeric = [float(value) for value in tokens[4:]]
    if not all(math.isfinite(value) for value in numeric):
        raise RuntimeError("candidate emitted non-finite values")
    scalar_count = nt * nmu
    tensor_count = scalar_count * 9
    expected = 2 * scalar_count + len(TENSOR_KEYS) * tensor_count
    if len(numeric) != expected:
        raise RuntimeError(f"candidate emitted {len(numeric)} values, expected {expected}")
    position = 0

    def scalars():
        nonlocal position
        result = []
        for _ in range(nt):
            result.append(numeric[position:position + nmu])
            position += nmu
        return result

    output = {
        "schema_version": 1,
        "name": name,
        "electron_count": scalars(),
        "carrier_density_cm3": scalars(),
    }
    for key in TENSOR_KEYS:
        matrix, consumed = _nested_matrix(numeric[position:], nt, nmu)
        position += consumed
        output[key] = matrix
    return output


class CandidateProgram:
    def __init__(self, testbed, driver):
        self.testbed = Path(testbed).resolve()
        self.driver = Path(driver).resolve()
        self._temporary = tempfile.TemporaryDirectory(prefix="transport-candidate-")
        self.binary = Path(self._temporary.name) / "transport-driver"
        source = self.testbed / MODULE
        if not source.is_file():
            raise FileNotFoundError(str(MODULE))
        completed = subprocess.run(
            [
                "gfortran", "-std=f2008", "-O2", "-Wall", "-Wextra",
                "-Werror=implicit-interface", "-fcheck=all",
                "-J", self._temporary.name,
                str(source), str(self.driver), "-o", str(self.binary),
            ],
            text=True,
            capture_output=True,
            cwd=self._temporary.name,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError("candidate compilation failed:\n" + completed.stderr[-5000:])

    def run(self, payload, timeout=30):
        completed = subprocess.run(
            [str(self.binary)],
            input=serialize(payload),
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"candidate process failed ({completed.returncode}): "
                + completed.stderr[-2000:]
            )
        return parse_output(completed.stdout, payload.get("name", "unnamed"))

    def close(self):
        self._temporary.cleanup()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", default="/testbed")
    parser.add_argument("--driver", default="/opt/candidate-runner/transport_driver.f90")
    args = parser.parse_args()
    payload = json.load(sys.stdin)
    program = CandidateProgram(args.testbed, args.driver)
    try:
        if isinstance(payload, dict) and isinstance(payload.get("cases"), list):
            output = []
            for case in payload["cases"]:
                try:
                    output.append({"ok": True, "output": program.run(case)})
                except Exception as exc:
                    output.append({"ok": False, "error": str(exc)[:2000]})
        else:
            output = program.run(payload)
        json.dump(output, sys.stdout, separators=(",", ":"), allow_nan=False)
        sys.stdout.write("\n")
    finally:
        program.close()


if __name__ == "__main__":
    main()
