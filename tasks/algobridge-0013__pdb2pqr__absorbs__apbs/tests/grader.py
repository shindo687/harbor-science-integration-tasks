#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0013."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

import numpy as np

from cases import hidden_cases, public_cases


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-apbs-source")
MODULE = Path("pdb2pqr/lpbe_grid.py")
LOCK = Path("/tests/source-lock.json")
FORBIDDEN = re.compile(
    r"\b(subprocess|ctypes|cffi|socket|requests|urllib|importlib|pickle)\b"
    r"|__import__|os\s*\.\s*system|\bpopen\s*\(|\bexec\s*\(|\beval\s*\("
    r"|\bopen\s*\(", re.IGNORECASE,
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(report, reward):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["reward"] = float(reward)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    REWARD.write_text(f"{float(reward):.10f}\n")


def fail(reason, report=None):
    report = {} if report is None else report
    report.update({"status": "hard_gate_failed", "reason": reason})
    write_report(report, 0.0)
    raise SystemExit(0)


def ignored(path):
    return (any(part.startswith(".") for part in path.parts)
            or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"})


def manifest(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if path.is_symlink():
            result[str(relative)] = "SYMLINK"
        elif path.is_file():
            result[str(relative)] = sha256(path)
    return result


def source_policy():
    candidate, pristine = manifest(TESTBED), manifest(PRISTINE)
    missing = sorted(set(pristine) - set(candidate))
    changed = sorted(name for name in set(pristine) & set(candidate)
                     if pristine[name] != candidate[name])
    added = sorted(set(candidate) - set(pristine))
    if missing:
        return False, f"host files removed: {missing[:4]}"
    if changed:
        return False, f"locked host files changed: {changed[:4]}"
    if set(added) != {str(MODULE)}:
        return False, f"unexpected added files: {added[:4]}"
    module = TESTBED / MODULE
    if not module.is_file() or module.is_symlink() or module.stat().st_size > 80_000:
        return False, "missing, linked, or oversized lpbe_grid.py"
    try:
        text = module.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError):
        return False, "candidate module is not valid UTF-8 Python"
    if FORBIDDEN.search(text):
        return False, "candidate contains a forbidden dependency or execution primitive"
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    if imports - {"__future__", "math", "numpy"}:
        return False, f"candidate imports unsupported modules: {sorted(imports)}"
    donor_hashes = {sha256(path) for path in DONOR.rglob("*")
                    if path.is_file() and path.stat().st_size <= 2_000_000}
    if sha256(module) in donor_hashes:
        return False, "candidate is a copied donor file"
    return True, {
        "added": added,
        "module_sha256": sha256(module),
        "module_bytes": module.stat().st_size,
        "allowed_import_scan": "pass",
        "forbidden_dependency_scan": "pass",
        "donor_file_hash_scan": "pass",
    }


def provenance_gate():
    lock = json.loads(LOCK.read_text())
    runtime = lock["reference_runtime"]
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["sha256"],
        "/opt/source-archives/donor-source.tar.gz": lock["donor"]["sha256"],
        "/opt/reference-apbs/APBS-3.4.1.Linux.zip": runtime["apbs_release_sha256"],
        "/opt/reference-wheels/" + runtime["numpy_wheel"]: runtime["numpy_wheel_sha256"],
    }
    for name, expected in checks.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            return False, f"provenance mismatch: {name}"
    executable = "/opt/reference-apbs/APBS-3.4.1.Linux/bin/apbs"
    completed = subprocess.run(
        [executable, "--version"], text=True, capture_output=True,
        timeout=30, check=False,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode not in (0, 13) or "APBS 3.4.1" not in output:
        return False, "locked APBS reference smoke check failed"
    return True, {"archive_asset_and_wheel_checks": len(checks),
                  "apbs_version": "3.4.1"}


def candidate_isolation_gate():
    protected = (
        "/tests", "/opt/reference-apbs", "/opt/reference-apbs-source",
        "/opt/reference-wheels", "/opt/pristine-host",
        "/opt/reference-runner", "/opt/source-archives",
    )
    readable = []
    for path in protected:
        completed = subprocess.run(
            ["runuser", "-u", "candidate", "--", "test", "-r", path],
            timeout=10, check=False,
        )
        if completed.returncode == 0:
            readable.append(path)
    if readable:
        return False, f"candidate can read protected paths: {readable}"
    return True, {"uid": 10001, "protected_paths_unreadable": list(protected)}


def run_one(command, payload, *, candidate=False, timeout=120):
    if candidate:
        command = [
            "runuser", "-u", "candidate", "--", "env",
            "PYTHONPATH=/opt/candidate-python", "PYTHONNOUSERSITE=1",
            "PYTHONDONTWRITEBYTECODE=1",
        ] + command
    completed = subprocess.run(
        command, input=json.dumps(payload, allow_nan=False) + "\n", text=True,
        capture_output=True, timeout=timeout, check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stderr[-1800:]}"
        )
    lines = completed.stdout.strip().splitlines()
    if len(lines) != 1:
        raise RuntimeError(f"expected one JSON line, got {len(lines)}")
    try:
        return json.loads(lines[0])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON output: {completed.stdout[-1800:]}") from exc


def invalid_cases(packet):
    result = []

    def add(name, edit):
        value = copy.deepcopy(packet)
        edit(value)
        result.append((name, value))

    add("invalid_schema", lambda x: x.update(schema="unknown"))
    add("invalid_dims_even", lambda x: x.update(dims=[16, 17, 17]))
    add("invalid_dims_small", lambda x: x.update(dims=[3, 17, 17]))
    add("invalid_spacing", lambda x: x.update(spacing=[1.0, 0.0, 1.0]))
    add("invalid_zmagic", lambda x: x.update(zmagic=0.0))
    add("invalid_zkappa2", lambda x: x.update(zkappa2=-1.0))
    add("invalid_grid_length", lambda x: x["charge"].pop())
    add("invalid_dielectric", lambda x: x["diel_x"].__setitem__(1, 0.0))
    add("invalid_kappa", lambda x: x["kappa"].__setitem__(2, 1.1))
    add("invalid_charge_nan", lambda x: x["charge"].__setitem__(3, None))
    add("invalid_tolerance", lambda x: x.update(relative_tolerance=0.1))
    add("invalid_iterations", lambda x: x.update(max_iterations=0))
    return result


def finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def residual_metrics(packet, potential):
    dims = tuple(packet["dims"])
    nx, ny, nz = dims
    hx, hy, hz = packet["spacing"]
    ex = np.asarray(packet["diel_x"]).reshape(dims)
    ey = np.asarray(packet["diel_y"]).reshape(dims)
    ez = np.asarray(packet["diel_z"]).reshape(dims)
    kappa = np.asarray(packet["kappa"]).reshape(dims)
    charge = np.asarray(packet["charge"]).reshape(dims)
    boundary = np.asarray(packet["boundary"]).reshape(dims)
    values = np.asarray(potential).reshape(dims)
    x_area, y_area, z_area = hy * hz / hx, hx * hz / hy, hx * hy / hz
    volume = hx * hy * hz
    cxp = ex[1:-1, 1:-1, 1:-1] * x_area
    cxm = ex[:-2, 1:-1, 1:-1] * x_area
    cyp = ey[1:-1, 1:-1, 1:-1] * y_area
    cym = ey[1:-1, :-2, 1:-1] * y_area
    czp = ez[1:-1, 1:-1, 1:-1] * z_area
    czm = ez[1:-1, 1:-1, :-2] * z_area
    diagonal = cxp + cxm + cyp + cym + czp + czm
    diagonal += packet["zkappa2"] * kappa[1:-1, 1:-1, 1:-1] * volume
    rhs = charge[1:-1, 1:-1, 1:-1] * packet["zmagic"] * volume
    rhs = rhs.copy()
    rhs[0] += cxm[0] * boundary[0, 1:-1, 1:-1]
    rhs[-1] += cxp[-1] * boundary[-1, 1:-1, 1:-1]
    rhs[:, 0] += cym[:, 0] * boundary[1:-1, 0, 1:-1]
    rhs[:, -1] += cyp[:, -1] * boundary[1:-1, -1, 1:-1]
    rhs[:, :, 0] += czm[:, :, 0] * boundary[1:-1, 1:-1, 0]
    rhs[:, :, -1] += czp[:, :, -1] * boundary[1:-1, 1:-1, -1]
    interior = values[1:-1, 1:-1, 1:-1]
    product = diagonal * interior
    product[:-1] -= cxp[:-1] * interior[1:]
    product[1:] -= cxm[1:] * interior[:-1]
    product[:, :-1] -= cyp[:, :-1] * interior[:, 1:]
    product[:, 1:] -= cym[:, 1:] * interior[:, :-1]
    product[:, :, :-1] -= czp[:, :, :-1] * interior[:, :, 1:]
    product[:, :, 1:] -= czm[:, :, 1:] * interior[:, :, :-1]
    absolute = float(np.linalg.norm((rhs - product).ravel()))
    relative = absolute / max(float(np.linalg.norm(rhs.ravel())), np.finfo(float).tiny)
    boundary_delta = 0.0
    for axis in range(3):
        for edge in (0, -1):
            observed = np.take(values, edge, axis=axis)
            wanted = np.take(boundary, edge, axis=axis)
            boundary_delta = max(boundary_delta, float(np.max(np.abs(observed - wanted))))
    return absolute, relative, boundary_delta


def compare_case(packet, expected, observed):
    reasons, metrics = [], {}
    try:
        if not isinstance(observed, dict) or set(observed) != {
                "schema", "dims", "potential", "energy_kj_mol", "diagnostics"}:
            return False, ["result_schema"], metrics
        if observed["schema"] != "algobridge-pdb2pqr-lpbe-result-v1":
            reasons.append("result_schema_version")
        if observed["dims"] != packet["dims"]:
            reasons.append("result_dims")
        potential = observed["potential"]
        if (not isinstance(potential, list) or len(potential) != math.prod(packet["dims"])
                or any(not finite(value) for value in potential)):
            return False, sorted(set(reasons + ["potential_schema"])), metrics
        expected_potential = np.asarray(expected["potential"], dtype=float)
        observed_potential = np.asarray(potential, dtype=float)
        potential_max_abs = float(np.max(np.abs(observed_potential - expected_potential)))
        metrics["potential_max_abs"] = potential_max_abs
        if potential_max_abs > 1.0e-4:
            reasons.append("potential_accuracy")
        energy = observed["energy_kj_mol"]
        if not finite(energy):
            reasons.append("energy_schema")
        else:
            energy_abs = abs(float(energy) - float(expected["energy_kj_mol"]))
            energy_limit = max(0.02, 2.0e-4 * max(1.0, abs(float(expected["energy_kj_mol"]))))
            metrics.update({"energy_abs": energy_abs, "energy_limit": energy_limit})
            if energy_abs > energy_limit:
                reasons.append("energy_accuracy")
            volume = math.prod(packet["spacing"])
            thermal = 1.3806581e-23 * packet["temperature"] * 1.0e-3 * 6.0221367e23
            recomputed = (0.5 * float(np.dot(np.asarray(packet["charge"]), observed_potential))
                          * volume * thermal)
            metrics["energy_self_consistency_abs"] = abs(float(energy) - recomputed)
            if abs(float(energy) - recomputed) > 1e-8 * max(1.0, abs(recomputed)):
                reasons.append("energy_self_consistency")
        absolute, relative, boundary_delta = residual_metrics(packet, potential)
        metrics.update({"independent_absolute_residual": absolute,
                        "independent_relative_residual": relative,
                        "boundary_max_abs": boundary_delta})
        if relative > 2.0e-9:
            reasons.append("linear_residual")
        if boundary_delta > 1.0e-12:
            reasons.append("boundary_values")
        diagnostics = observed["diagnostics"]
        required = {"converged", "iterations", "absolute_residual",
                    "relative_residual", "residual_history"}
        if not isinstance(diagnostics, dict) or set(diagnostics) != required:
            reasons.append("diagnostics_schema")
        else:
            history = diagnostics["residual_history"]
            if (diagnostics["converged"] is not True
                    or type(diagnostics["iterations"]) is not int
                    or not 0 <= diagnostics["iterations"] <= packet["max_iterations"]
                    or not finite(diagnostics["absolute_residual"])
                    or not finite(diagnostics["relative_residual"])
                    or not isinstance(history, list) or not history
                    or any(not finite(value) or value < 0 for value in history)):
                reasons.append("diagnostics_values")
            elif (abs(float(diagnostics["relative_residual"]) - relative)
                  > max(1e-13, relative * 1e-3)):
                reasons.append("diagnostics_residual")
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        reasons.append(f"malformed:{type(exc).__name__}")
    return not reasons, sorted(set(reasons)), metrics


def close_vectors(first, second, *, sign=1.0, tolerance=1e-8):
    if not isinstance(first, list) or not isinstance(second, list) or len(first) != len(second):
        return False
    return max((abs(float(a) - sign * float(b)) for a, b in zip(first, second)), default=0.0) <= tolerance


def main():
    report = {"task": "ALGOBRIDGE-0013"}
    for name, gate in (("source_policy", source_policy),
                       ("provenance", provenance_gate),
                       ("candidate_isolation", candidate_isolation_gate)):
        ok, detail = gate()
        report[name] = detail
        if not ok:
            fail(str(detail), report)

    candidate_command = ["python", "/opt/candidate-runner/candidate_runner.py"]
    reference_command = ["python", "/opt/reference-runner/reference_runner.py"]
    descriptions = public_cases() + hidden_cases()
    expected_rows = []
    try:
        for description in descriptions:
            answer = run_one(reference_command, {"description": description}, timeout=60)
            if answer.get("ok") is not True:
                fail(f"native APBS reference failed: {answer.get('error')}", report)
            expected_rows.append(answer["result"])
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        fail(f"native APBS reference failed: {type(exc).__name__}: {exc}", report)

    invalid = invalid_cases(expected_rows[0]["packet"])
    invalid_rows = []
    for name, packet in invalid:
        try:
            result = run_one(candidate_command, {"packet": packet}, candidate=True, timeout=60)
            invalid_rows.append({"name": name, "passed": result.get("ok") is False})
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            invalid_rows.append({"name": name, "passed": False})
    invalid_passed = sum(row["passed"] for row in invalid_rows)
    report["invalid_contract"] = {"passed": invalid_passed, "total": len(invalid_rows),
                                  "cases": invalid_rows}
    if invalid_passed != len(invalid_rows):
        fail("invalid-input contract gate failed", report)

    rows = []
    for expected in expected_rows:
        try:
            got = run_one(candidate_command, {"packet": expected["packet"]},
                          candidate=True, timeout=120)
            if got.get("ok") is not True:
                rows.append({"name": expected["name"], "passed": False,
                             "reasons": [f"candidate_{got.get('error', 'error')}"]})
            else:
                passed, reasons, metrics = compare_case(
                    expected["packet"], expected["expected"], got["result"])
                rows.append({"name": expected["name"], "passed": passed,
                             "reasons": reasons, "metrics": metrics})
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
            rows.append({"name": expected["name"], "passed": False,
                         "reasons": [f"runner_{type(exc).__name__}"]})

    base = expected_rows[0]["packet"]
    scaled = copy.deepcopy(base)
    factor = 3.7
    for name in ("diel_x", "diel_y", "diel_z"):
        scaled[name] = [factor * value for value in scaled[name]]
    scaled["zkappa2"] *= factor
    scaled["zmagic"] *= factor
    signed = copy.deepcopy(base)
    signed["charge"] = [-value for value in signed["charge"]]
    signed["boundary"] = [-value for value in signed["boundary"]]
    meta_rows = []
    try:
        original = run_one(candidate_command, {"packet": base}, candidate=True)["result"]
        scaled_result = run_one(candidate_command, {"packet": scaled}, candidate=True)["result"]
        scaled_ok = (close_vectors(original["potential"], scaled_result["potential"])
                     and abs(original["energy_kj_mol"] - scaled_result["energy_kj_mol"])
                     <= 1e-8 * max(1.0, abs(original["energy_kj_mol"])))
        meta_rows.append({"name": "operator_source_scale_homogeneity", "passed": scaled_ok})
        signed_result = run_one(candidate_command, {"packet": signed}, candidate=True)["result"]
        signed_ok = (close_vectors(original["potential"], signed_result["potential"], sign=-1.0)
                     and abs(original["energy_kj_mol"] - signed_result["energy_kj_mol"])
                     <= 1e-8 * max(1.0, abs(original["energy_kj_mol"])))
        meta_rows.append({"name": "charge_boundary_sign_inversion", "passed": signed_ok})
    except (KeyError, OSError, RuntimeError, subprocess.TimeoutExpired):
        meta_rows = [{"name": "operator_source_scale_homogeneity", "passed": False},
                     {"name": "charge_boundary_sign_inversion", "passed": False}]
    meta_passed = sum(row["passed"] for row in meta_rows)
    report["metamorphic"] = {"passed": meta_passed, "total": 2, "cases": meta_rows}
    if meta_passed != 2:
        fail("metamorphic contract gate failed", report)

    public_count = len(public_cases())
    public_rows, hidden_rows = rows[:public_count], rows[public_count:]
    public_passed = sum(row["passed"] for row in public_rows)
    hidden_passed = sum(row["passed"] for row in hidden_rows)
    reward = (public_passed + hidden_passed) / len(rows)
    report.update({
        "status": "graded",
        "reference": "official APBS 3.4.1 uniform-grid LPBE (root-only)",
        "candidate_identity": {"uid": 10001, "reference_paths_readable": False},
        "public": {"passed": public_passed, "total": len(public_rows),
                   "cases": public_rows},
        "hidden": {"passed": hidden_passed, "total": len(hidden_rows),
                   "cases": hidden_rows},
    })
    write_report(report, reward)


if __name__ == "__main__":
    main()
