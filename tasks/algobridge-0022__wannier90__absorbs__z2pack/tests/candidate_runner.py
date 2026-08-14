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

MODULE = Path(os.environ.get("Z2_CANDIDATE_MODULE", "/testbed/src/z2_wilson_loop.F90"))
DRIVER = Path(os.environ.get("Z2_CANDIDATE_DRIVER", "/opt/candidate-runner/z2_wilson_driver.f90"))
CACHE = Path("/tmp/z2-wilson-candidate")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
USE_PRIVDROP = os.geteuid() == 0 and os.environ.get("Z2_CANDIDATE_NO_PRIVDROP") != "1"


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
        resource.setrlimit(resource.RLIMIT_CPU, (60, 60))
        resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))


def _validated_mesh(path: Path) -> tuple[dict, list[complex]]:
    case = json.loads(path.read_text())
    if case.get("schema") != "wannier90-z2-mesh-v1":
        raise ValueError("unsupported schema")
    if case.get("num_orbitals") != 4 or case.get("num_occupied") != 2:
        raise ValueError("only 4 orbitals and 2 occupied bands are supported")
    nlines, nk = case.get("num_lines"), case.get("loop_points")
    tol = case.get("gap_tolerance")
    if not isinstance(nlines, int) or nlines < 3:
        raise ValueError("num_lines must be at least 3")
    if not isinstance(nk, int) or nk < 6:
        raise ValueError("loop_points must be at least 6")
    if not isinstance(tol, (float, int)) or not math.isfinite(tol) or tol <= 0:
        raise ValueError("gap_tolerance must be finite and positive")
    raw = case.get("hamiltonians")
    if not isinstance(raw, list) or len(raw) != nlines:
        raise ValueError("invalid Hamiltonian line count")
    mesh: list[complex] = []
    for line in raw:
        if not isinstance(line, list) or len(line) != nk:
            raise ValueError("invalid Hamiltonian loop count")
        for matrix in line:
            if not isinstance(matrix, list) or len(matrix) != 4:
                raise ValueError("Hamiltonian must be 4 by 4")
            converted: list[list[complex]] = []
            for row in matrix:
                if not isinstance(row, list) or len(row) != 4:
                    raise ValueError("Hamiltonian must be 4 by 4")
                converted_row = []
                for pair in row:
                    if not isinstance(pair, list) or len(pair) != 2:
                        raise ValueError("matrix entries must be [real, imag]")
                    value = complex(float(pair[0]), float(pair[1]))
                    if not math.isfinite(value.real) or not math.isfinite(value.imag):
                        raise ValueError("non-finite Hamiltonian")
                    converted_row.append(value)
                    mesh.append(value)
                converted.append(converted_row)
            for a in range(4):
                for b in range(4):
                    if abs(converted[a][b] - converted[b][a].conjugate()) > 1e-10:
                        raise ValueError("non-Hermitian Hamiltonian")
    return case, mesh


def _binary() -> Path:
    if not MODULE.is_file():
        raise FileNotFoundError("candidate did not add src/z2_wilson_loop.F90")
    digest = hashlib.sha256(MODULE.read_bytes() + DRIVER.read_bytes()).hexdigest()[:20]
    binary = CACHE / digest / "z2_wilson_driver"
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
        ["gfortran", "-std=f2008", "-O2", "-Wall", "-Wextra", "-fcheck=all",
         str(MODULE), str(DRIVER), "-o", str(build / "z2_wilson_driver")],
        text=True, capture_output=True, timeout=120, cwd=build,
        preexec_fn=(lambda: _drop_privileges(compile_step=True)) if USE_PRIVDROP else None,
    )
    if proc.returncode:
        raise RuntimeError("candidate compile failed:\n" + proc.stdout + proc.stderr)
    binary.parent.mkdir(parents=True, exist_ok=True)
    os.replace(build / "z2_wilson_driver", binary)
    binary.chmod(0o755)
    shutil.rmtree(build, ignore_errors=True)
    return binary


def run_candidate(path: Path) -> dict:
    case, mesh = _validated_mesh(path)
    with tempfile.NamedTemporaryFile("w", delete=False) as stream:
        stream.write(f"4 2 {case['num_lines']} {case['loop_points']}\n")
        stream.write(f"{float(case['gap_tolerance']):.17e}\n")
        for value in mesh:
            stream.write(f"{value.real:.17e} {value.imag:.17e}\n")
        stream_path = stream.name
    try:
        run_dir = Path(tempfile.mkdtemp(prefix="z2-candidate-run-"))
        if USE_PRIVDROP:
            os.chown(run_dir, CANDIDATE_UID, CANDIDATE_GID)
        with open(stream_path, "r", encoding="utf-8") as stdin:
            proc = subprocess.run(
                [str(_binary())], stdin=stdin, text=True, capture_output=True, timeout=120,
                cwd=run_dir, preexec_fn=_drop_privileges if USE_PRIVDROP else None,
            )
        if proc.returncode:
            raise RuntimeError(f"candidate exited {proc.returncode}: {proc.stderr}")
        lines = [line for line in proc.stdout.splitlines() if line.strip()]
        if len(lines) != 1:
            raise RuntimeError(f"candidate must print one JSON line, got: {proc.stdout!r}")
        return json.loads(lines[0])
    finally:
        Path(stream_path).unlink(missing_ok=True)
        if "run_dir" in locals():
            shutil.rmtree(run_dir, ignore_errors=True)


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: candidate_runner.py CASE.json", file=sys.stderr)
        return 2
    try:
        result = run_candidate(Path(sys.argv[1]))
    except Exception as exc:
        result = {"status": "invalid_input", "error": str(exc)}
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
