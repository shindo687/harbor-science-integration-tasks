#!/usr/bin/env python3
"""Isolated dynamic differential verifier for ALGOBRIDGE-0015."""

from __future__ import annotations

import difflib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tokenize

import numpy as np

from cases import hidden_cases, invalid_cases


TESTBED = Path("/testbed")
TESTS = Path("/tests")
LOG_ROOT = Path("/logs/verifier")
REFERENCE_HOST = Path("/opt/reference-host")
REFERENCE_DONOR = Path("/opt/reference-donor")
PRISTINE_HOST = Path("/opt/pristine-host")
REFERENCE_RUNNER = Path("/opt/reference-runner/reference_runner.py")
CANDIDATE_RUNNER = Path("/opt/candidate-runner/candidate_runner.py")
CANDIDATE_RUNTIME = Path("/opt/candidate-runtime")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
HOST_ARCHIVE_SHA256 = "dfbb5c7b115dc5f5c96358561773a5ed6595f3fc5ff9aed16e06a7682a1b111d"
DONOR_ARCHIVE_SHA256 = "d0e815a1bc88912cb0cb9c64bdb2ffc75eaec6f5225e79bd016acd5cbcf60a17"
HOST_COMMIT = "c6173db6e8edd705eb59172bd21e9ce69c572405"
DONOR_COMMIT = "ed40ec3bbef03bb08938ad1a74d459b0d1ab81f7"
ALLOWED_FILES = {
    "wrappers/python/openmm/app/mbar.py",
    "wrappers/python/openmm/app/__init__.py",
}
ALLOWED_PREFIXES = ("wrappers/python/tests/",)


def log(message):
    print(message, flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def demote():
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def run_json(command, payload, env, *, candidate=False, timeout=900):
    completed = subprocess.run(
        command,
        input=json.dumps(payload, allow_nan=False),
        text=True,
        capture_output=True,
        cwd="/tmp/candidate-home" if candidate else "/tmp",
        env=env,
        preexec_fn=demote if candidate and os.getuid() == 0 else None,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"runner exited {completed.returncode}: stdout={completed.stdout[-3000:]} "
            f"stderr={completed.stderr[-4000:]}"
        )
    return json.loads(completed.stdout), completed.stderr


def verify_reference_integrity():
    failures = []
    lock = json.loads((TESTS / "source-lock.json").read_text())
    if lock["host"]["commit"] != HOST_COMMIT:
        failures.append("host commit lock")
    if lock["donor"]["commit"] != DONOR_COMMIT:
        failures.append("donor commit lock")
    if lock["host"]["snapshot_sha256"] != HOST_ARCHIVE_SHA256:
        failures.append("host snapshot identity")
    if lock["donor"]["snapshot_sha256"] != DONOR_ARCHIVE_SHA256:
        failures.append("donor snapshot identity")
    archives = Path("/opt/source-archives")
    if digest(archives / "host-source.tar.gz") != HOST_ARCHIVE_SHA256:
        failures.append("host archive digest")
    if digest(archives / "donor-source.tar.gz") != DONOR_ARCHIVE_SHA256:
        failures.append("donor archive digest")
    required = [
        REFERENCE_HOST / "CMakeLists.txt",
        REFERENCE_DONOR / "pymbar/mbar.py",
        PRISTINE_HOST / "wrappers/python/openmm/app/__init__.py",
    ]
    failures.extend(f"missing reference file: {path}" for path in required if not path.is_file())
    return failures


def normalized_tokens(path):
    tokens = []
    try:
        with path.open("rb") as handle:
            for item in tokenize.tokenize(handle.readline):
                if item.type not in {
                    tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                    tokenize.COMMENT, tokenize.STRING,
                }:
                    tokens.append(item.string)
    except (OSError, tokenize.TokenError, SyntaxError, IndentationError):
        return []
    return tokens


def donor_fragments():
    fragments = set()
    for path in REFERENCE_DONOR.rglob("*.py"):
        tokens = normalized_tokens(path)
        for size in (48, 64):
            fragments.update(tuple(tokens[i:i + size]) for i in range(len(tokens)-size+1))
    return fragments


def ignored(relative):
    parts = Path(relative).parts
    return any(part in {".git", "__pycache__", ".pytest_cache", "build", "dist"}
               for part in parts)


def source_scan(fragments):
    forbidden = re.compile(
        r"(?:\bpymbar\b|/opt/|/tests|reference_runner|\bsubprocess\b|\bctypes\b|"
        r"\bcffi\b|\bsocket\b|\burllib\b|\brequests\b|\bscipy\b|\bnumexpr\b|"
        r"\bpickle\b|\bmarshal\b)", re.IGNORECASE,
    )
    findings, changed = [], []
    pristine_files = {
        str(path.relative_to(PRISTINE_HOST)): path
        for path in PRISTINE_HOST.rglob("*") if path.is_file()
    }
    candidate_files = {
        str(path.relative_to(TESTBED)): path
        for path in TESTBED.rglob("*") if path.is_file()
    }
    for relative in sorted(set(pristine_files) | set(candidate_files)):
        if ignored(relative):
            continue
        pristine = pristine_files.get(relative)
        candidate = candidate_files.get(relative)
        if pristine is not None and candidate is not None and candidate.read_bytes() == pristine.read_bytes():
            continue
        changed.append(relative)
        if relative not in ALLOWED_FILES and not relative.startswith(ALLOWED_PREFIXES):
            findings.append(f"changed outside allowed surface: {relative}")
        if candidate is None:
            findings.append(f"deleted locked host file: {relative}")
            continue
        data = candidate.read_bytes()
        if len(data) > 500_000 or b"\0" in data:
            findings.append(f"invalid changed file: {relative}")
            continue
        text = data.decode("utf-8", errors="replace")
        scan_text = text
        if pristine is not None:
            scan_text = "\n".join(
                line[1:] for line in difflib.unified_diff(
                    pristine.read_text(errors="replace").splitlines(), text.splitlines()
                ) if line.startswith("+") and not line.startswith("+++")
            )
        match = forbidden.search(scan_text)
        if match:
            findings.append(f"forbidden reference in {relative}: {match.group(0)!r}")
        if candidate.suffix == ".py":
            tokens = normalized_tokens(candidate)
            for size in (64, 48):
                if any(tuple(tokens[i:i+size]) in fragments for i in range(len(tokens)-size+1)):
                    findings.append(f"donor token fragment ({size}) in {relative}")
                    break
    if "wrappers/python/openmm/app/mbar.py" not in changed:
        findings.append("missing native OpenMM MBAR module")
    if "wrappers/python/openmm/app/__init__.py" not in changed:
        findings.append("missing OpenMM public API export")
    return findings, changed


def materialize_candidate():
    completed = subprocess.run(
        [sys.executable, "/opt/candidate-tools/materialize_candidate.py"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"candidate materialization failed: {completed.stderr[-3000:]}")
    return (CANDIDATE_RUNTIME / "OVERLAY-MANIFEST.txt").read_text().splitlines()


def destroy_private_material():
    paths = [
        REFERENCE_HOST, REFERENCE_DONOR, PRISTINE_HOST,
        Path("/opt/reference-runner"), Path("/opt/source-archives"),
        Path("/opt/wheels"), Path("/opt/candidate-tools"),
        Path("/opt/installed-openmm"),
    ]
    for path in paths:
        if path.exists():
            shutil.rmtree(path)
    if any(path.exists() for path in paths):
        raise RuntimeError("private material deletion failed")


def lock_candidate():
    for path in (TESTBED, CANDIDATE_RUNTIME):
        subprocess.run(["chown", "-R", "root:root", str(path)], check=True)
        subprocess.run(["chmod", "-R", "a-w", str(path)], check=True)


def reference_env():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/reference-donor:/opt/reference-runner:/tests",
        "PYTHONNOUSERSITE": "1", "HOME": "/tmp", "PYMBAR_DISABLE_JAX": "1",
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
    }


def candidate_env():
    home = Path("/tmp/candidate-home")
    home.mkdir(exist_ok=True)
    os.chown(home, CANDIDATE_UID, CANDIDATE_GID)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/candidate-runtime:/opt/candidate-runner",
        "PYTHONNOUSERSITE": "1", "HOME": str(home), "TMPDIR": str(home),
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
    }


def array_error(expected, observed):
    left = np.asarray(expected, dtype=float)
    right = np.asarray(observed, dtype=float)
    if left.shape != right.shape or not np.all(np.isfinite(right)):
        return math.inf, math.inf
    absolute = float(np.max(np.abs(left-right))) if left.size else 0.0
    scale = np.maximum(1.0, np.abs(left))
    relative = float(np.max(np.abs(left-right)/scale)) if left.size else 0.0
    return absolute, relative


def compare_case(expected, observed, n_k):
    details = {}
    thresholds = {
        "f_k": (2e-8, 2e-9),
        "Delta_f": (3e-8, 2e-9),
        "weights": (3e-8, 3e-8),
        "overlap": (3e-7, 3e-7),
        "effective_sample_number": (3e-5, 3e-7),
        "covariance": (3e-5, 3e-6),
        "dDelta_f": (3e-5, 3e-6),
    }
    passed = True
    for key, (abs_tol, rel_tol) in thresholds.items():
        absolute, relative = array_error(expected[key], observed[key])
        details[f"{key}_max_abs"] = absolute
        details[f"{key}_max_scaled"] = relative
        passed &= absolute <= abs_tol or relative <= rel_tol

    f_k = np.asarray(observed["f_k"], dtype=float)
    delta = np.asarray(observed["Delta_f"], dtype=float)
    covariance = np.asarray(observed["covariance"], dtype=float)
    weights = np.asarray(observed["weights"], dtype=float)
    overlap = np.asarray(observed["overlap"], dtype=float)
    effective = np.asarray(observed["effective_sample_number"], dtype=float)
    n_k = np.asarray(n_k, dtype=float)
    scientific = (
        abs(f_k[0]) <= 1e-10
        and np.allclose(delta, -delta.T, rtol=0, atol=2e-10)
        and np.allclose(delta, f_k[None, :] - f_k[:, None], rtol=0, atol=2e-10)
        and np.allclose(weights.sum(axis=0), 1.0, rtol=0, atol=2e-9)
        and np.allclose(weights @ n_k, 1.0, rtol=0, atol=2e-9)
        and np.allclose(overlap.sum(axis=1), 1.0, rtol=0, atol=2e-8)
        and np.allclose(covariance, covariance.T, rtol=0, atol=2e-9)
        and np.linalg.eigvalsh(covariance).min() >= -2e-8
        and np.allclose(effective, 1.0/np.sum(weights*weights, axis=0),
                        rtol=2e-8, atol=2e-8)
        and bool(observed["converged"])
        and int(observed["iterations"]) >= 0
        and float(observed["residual"]) <= 5e-8
    )
    details["scientific_invariants"] = bool(scientific)
    passed &= scientific
    return bool(passed), details


def run_regression(env):
    code = r'''
import numpy as np
from openmm import Context, CustomExternalForce, Platform, System, VerletIntegrator, Vec3
from openmm import unit
from openmm.app import estimate_mbar
s = System(); s.addParticle(1.0)
f = CustomExternalForce("x*x"); f.addParticle(0, []); s.addForce(f)
i = VerletIntegrator(0.001)
c = Context(s, i, Platform.getPlatformByName("Reference"))
c.setPositions([Vec3(0.25, 0, 0)]*unit.nanometer)
e = c.getState(getEnergy=True).getPotentialEnergy().value_in_unit(unit.kilojoule_per_mole)
assert abs(e-0.0625) < 1e-12
r = estimate_mbar([[0.0, 1.0], [1.0, 0.0]], [1, 1])
assert np.asarray(r["weights"]).shape == (2, 2)
'''
    completed = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True,
        cwd="/tmp/candidate-home", env=env, preexec_fn=demote, timeout=180, check=False,
    )
    return completed.returncode == 0, completed.stderr[-3000:]


def write_results(report, reward):
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    (LOG_ROOT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    (LOG_ROOT / "reward.txt").write_text(f"{reward:.12g}\n")


def main():
    report = {"task": "ALGOBRIDGE-0015", "hard_gates": {}, "points": []}
    try:
        integrity = verify_reference_integrity()
        report["hard_gates"]["reference_integrity"] = not integrity
        report["reference_integrity_findings"] = integrity
        fragments = donor_fragments()
        findings, changed = source_scan(fragments)
        report["hard_gates"]["source_policy"] = not findings
        report["source_findings"] = findings
        report["changed_files"] = changed
        if integrity or findings:
            write_results(report, 0.0)
            return

        reference, reference_stderr = run_json(
            [sys.executable, str(REFERENCE_RUNNER)], {"cases": hidden_cases()},
            reference_env(), timeout=900,
        )
        report["reference_runtime"] = reference["openmm_version"]
        report["reference_stderr_tail"] = reference_stderr[-2000:]

        overlay = materialize_candidate()
        report["overlay_manifest"] = overlay
        report["hard_gates"]["candidate_materialized"] = True
        destroy_private_material()
        lock_candidate()
        isolation = not any(path.exists() for path in (
            REFERENCE_HOST, REFERENCE_DONOR, PRISTINE_HOST,
            Path("/opt/reference-runner"), Path("/opt/source-archives"),
        ))
        report["hard_gates"]["reference_isolation"] = isolation
        if not isolation:
            write_results(report, 0.0)
            return

        env = candidate_env()
        regression_ok, regression_stderr = run_regression(env)
        report["hard_gates"]["host_regression"] = regression_ok
        report["regression_stderr_tail"] = regression_stderr
        if not regression_ok:
            write_results(report, 0.0)
            return

        numeric_inputs = [item["input"] for item in reference["cases"]]
        request_cases = numeric_inputs + invalid_cases()
        candidate, candidate_stderr = run_json(
            [sys.executable, str(CANDIDATE_RUNNER)], {"cases": request_cases},
            env, candidate=True, timeout=900,
        )
        report["candidate_stderr_tail"] = candidate_stderr[-2000:]
        if len(candidate["cases"]) != 15:
            raise RuntimeError("candidate returned wrong case count")
        report["hard_gates"]["candidate_protocol"] = True

        for ref_item, observed_item in zip(reference["cases"], candidate["cases"][:12], strict=True):
            if "result" not in observed_item:
                passed, details = False, {"error": observed_item.get("error", "missing result")}
            else:
                passed, details = compare_case(
                    ref_item["expected"], observed_item["result"], ref_item["input"]["N_k"]
                )
            report["points"].append({"name": ref_item["input"]["name"],
                                     "passed": passed, "details": details})

        for expected_case, observed_item in zip(invalid_cases(), candidate["cases"][12:], strict=True):
            passed = "error" in observed_item and "result" not in observed_item
            report["points"].append({"name": expected_case["name"], "passed": passed,
                                     "details": {"error": observed_item.get("error")}})

        by_name = {item["name"]: item for item in candidate["cases"] if "result" in item}
        if {"large_state_offsets", "common_sample_offsets"} <= by_name.keys():
            base = by_name["large_state_offsets"]["result"]
            shifted = by_name["common_sample_offsets"]["result"]
            invariant = (
                np.allclose(base["Delta_f"], shifted["Delta_f"], rtol=0, atol=3e-8)
                and np.allclose(base["weights"], shifted["weights"], rtol=0, atol=3e-8)
            )
            report["metamorphic_common_offset"] = bool(invariant)
            if not invariant:
                for point in report["points"]:
                    if point["name"] == "common_sample_offsets":
                        point["passed"] = False
                        point["details"]["common_offset_invariance"] = False

        passed_count = sum(item["passed"] for item in report["points"])
        reward = passed_count / 15.0
        report["passed"] = passed_count
        report["total"] = 15
        report["reward"] = reward
        write_results(report, reward)
        log(f"ALGOBRIDGE-0015: {passed_count}/15, reward={reward:.6f}")
    except Exception as exc:
        report["fatal_error"] = f"{type(exc).__name__}: {exc}"
        write_results(report, 0.0)
        log(report["fatal_error"])


if __name__ == "__main__":
    main()

