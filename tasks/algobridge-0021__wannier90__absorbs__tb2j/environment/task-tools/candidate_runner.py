#!/usr/bin/env python3
"""Compile and invoke the candidate's native Wannier90-side module."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile


MODULE = Path(os.environ.get(
    "EXCHANGE_CANDIDATE_MODULE", "/testbed/src/liechtenstein_exchange.F90"
)).resolve()
DRIVER = Path(os.environ.get(
    "EXCHANGE_CANDIDATE_DRIVER", "/opt/candidate-runner/liechtenstein_driver.f90"
)).resolve()
CACHE = Path("/tmp/liechtenstein-exchange-candidate")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
USE_PRIVDROP = os.geteuid() == 0 and os.environ.get("EXCHANGE_NO_PRIVDROP") != "1"


def _drop_privileges(*, compile_step: bool = False) -> None:
    if not USE_PRIVDROP:
        return
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
    if not compile_step:
        resource.setrlimit(resource.RLIMIT_CPU, (90, 90))
        resource.setrlimit(
            resource.RLIMIT_AS,
            (1024 * 1024 * 1024, 1024 * 1024 * 1024),
        )


def _matrix(case: dict, key: str, *, hermitian: bool) -> list[list[complex]]:
    raw = case.get(key)
    if not isinstance(raw, list) or len(raw) != 2:
        raise ValueError(f"{key} must be 2 by 2")
    matrix = []
    for row in raw:
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError(f"{key} must be 2 by 2")
        converted = []
        for pair in row:
            if not isinstance(pair, list) or len(pair) != 2:
                raise ValueError(f"{key} entries must be [real, imag]")
            value = complex(float(pair[0]), float(pair[1]))
            if not math.isfinite(value.real) or not math.isfinite(value.imag):
                raise ValueError(f"{key} contains non-finite values")
            if abs(value) > 10.0:
                raise ValueError(f"{key} exceeds the bounded 10 eV magnitude")
            converted.append(value)
        matrix.append(converted)
    if hermitian:
        for i in range(2):
            for j in range(2):
                if abs(matrix[i][j] - matrix[j][i].conjugate()) > 1.0e-11:
                    raise ValueError(f"{key} is not Hermitian")
    return matrix


def _validated_case(path: Path) -> tuple[dict, list[list[list[complex]]]]:
    case = json.loads(path.read_text())
    if case.get("schema") != "wannier90-tb2j-exchange-v1":
        raise ValueError("unsupported schema")
    if case.get("num_sites") != 2 or case.get("num_orbitals") != 2:
        raise ValueError("only two sites and two orbitals are supported")
    nk, nz = case.get("kmesh"), case.get("contour_points")
    if not isinstance(nk, int) or nk < 5 or nk > 13 or nk % 2 != 1:
        raise ValueError("kmesh must be an odd integer from 5 through 13")
    if not isinstance(nz, int) or nz < 32 or nz > 128:
        raise ValueError("contour_points must be an integer from 32 through 128")
    efermi, smearing = case.get("fermi_energy"), case.get("smearing")
    if (not isinstance(efermi, (int, float)) or not math.isfinite(efermi)
            or abs(float(efermi)) > 5.0):
        raise ValueError("fermi_energy must be finite and bounded by 5 eV")
    if (not isinstance(smearing, (int, float)) or not math.isfinite(smearing)
            or not 0.005 <= float(smearing) <= 0.2):
        raise ValueError("smearing must be finite and between 0.005 and 0.2 eV")
    matrices = [
        _matrix(case, "h0_up", hermitian=True),
        _matrix(case, "h1_up", hermitian=False),
        _matrix(case, "h0_down", hermitian=True),
        _matrix(case, "h1_down", hermitian=False),
    ]
    return case, matrices


def _binary() -> Path:
    if not MODULE.is_file():
        raise FileNotFoundError("candidate did not add src/liechtenstein_exchange.F90")
    digest = hashlib.sha256(MODULE.read_bytes() + DRIVER.read_bytes()).hexdigest()[:20]
    binary = CACHE / digest / "liechtenstein_driver"
    if binary.is_file():
        return binary
    CACHE.mkdir(parents=True, exist_ok=True)
    CACHE.chmod(0o755)
    build = CACHE / (digest + ".build")
    shutil.rmtree(build, ignore_errors=True)
    build.mkdir(parents=True)
    if USE_PRIVDROP:
        os.chown(build, CANDIDATE_UID, CANDIDATE_GID)
    proc = subprocess.run(
        [
            "gfortran", "-std=f2008", "-O2", "-Wall", "-Wextra",
            "-fcheck=all", str(MODULE), str(DRIVER), "-o",
            str(build / "liechtenstein_driver"),
        ],
        text=True,
        capture_output=True,
        timeout=120,
        cwd=build,
        preexec_fn=(lambda: _drop_privileges(compile_step=True)) if USE_PRIVDROP else None,
    )
    if proc.returncode:
        raise RuntimeError("candidate compile failed:\n" + proc.stdout + proc.stderr)
    binary.parent.mkdir(parents=True, exist_ok=True)
    os.replace(build / "liechtenstein_driver", binary)
    binary.chmod(0o755)
    shutil.rmtree(build, ignore_errors=True)
    return binary


def run_candidate(path: Path) -> dict:
    case, matrices = _validated_case(path)
    lines = [
        f"{case['kmesh']} {case['contour_points']} "
        f"{float(case['fermi_energy']):.17e} {float(case['smearing']):.17e}"
    ]
    for matrix in matrices:
        for i in range(2):
            for j in range(2):
                value = matrix[i][j]
                lines.append(f"{value.real:.17e} {value.imag:.17e}")
    run_dir = Path(tempfile.mkdtemp(prefix="exchange-candidate-run-"))
    try:
        if USE_PRIVDROP:
            os.chown(run_dir, CANDIDATE_UID, CANDIDATE_GID)
        proc = subprocess.run(
            [str(_binary())],
            input="\n".join(lines) + "\n",
            text=True,
            capture_output=True,
            timeout=120,
            cwd=run_dir,
            preexec_fn=_drop_privileges if USE_PRIVDROP else None,
        )
        if proc.returncode:
            raise RuntimeError(f"candidate exited {proc.returncode}: {proc.stderr}")
        output = [line for line in proc.stdout.splitlines() if line.strip()]
        if len(output) != 1:
            raise RuntimeError(f"candidate must print one JSON line, got: {proc.stdout!r}")
        return json.loads(output[0])
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: candidate_runner.py CASE.json", file=sys.stderr)
        return 2
    try:
        result = run_candidate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"status": "invalid_input", "error": str(exc)}
    print(json.dumps(result, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
