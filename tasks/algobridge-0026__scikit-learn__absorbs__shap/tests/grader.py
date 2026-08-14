#!/usr/bin/env python3
"""Separate clean-room differential verifier for ALGOBRIDGE-0026."""

from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time

import numpy as np

from cases import hidden_cases, invariant_cases


TESTBED = pathlib.Path("/testbed")
LOG_ROOT = pathlib.Path("/logs/verifier")
REFERENCE_PYTHON = "/opt/reference-venv/bin/python"
REFERENCE_RUNNER = "/opt/reference-runner/reference_runner.py"
CANDIDATE_RUNNER = "/opt/candidate-runner/candidate_runner.py"
PRISTINE_HOST = pathlib.Path("/opt/pristine-host")
CANDIDATE_RUNTIME = pathlib.Path("/opt/candidate-runtime")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
ATOL = 1e-9
RTOL = 1e-9
LOCKED_HOST_COMMIT = "e27ccf58592fcfe8c7ca87f53dde840c436093b2"
LOCKED_HOST_TREE = "87223e64df8880951bc88ee6049a8bf453dccf88"
LOCKED_DONOR_COMMIT = "df974a1966294b9c7acebb1373fd6dc5445d1d3d"
LOCKED_DONOR_TREE = "4ec180cdefa828142ec4e6da5c2b0c80697bf8e8"
LOCKED_SHAP_WHEEL = "shap-0.52.1.dev42-cp312-abi3-linux_x86_64.whl"
LOCKED_SHAP_WHEEL_SHA256 = "0321cb5f92a235af58982a9d36c58634125764cc10d0298fff6742c8c4465165"

CASE_POINTS = [case["name"] for case in hidden_cases()]
GATE_POINTS = ["scientific_invariants", "api_isolation_and_host_regression"]
POINT_NAMES = CASE_POINTS + GATE_POINTS


def log(message):
    print(message, flush=True)


def demote():
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def run_json(command, payload, *, env, candidate=False, timeout=600):
    completed = subprocess.run(
        command,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=demote if candidate and os.getuid() == 0 else None,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command}\n"
            f"stdout={completed.stdout[-3000:]}\nstderr={completed.stderr[-4000:]}"
        )
    try:
        return json.loads(completed.stdout), completed.stderr
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"runner returned non-JSON: {completed.stdout[-4000:]}\n"
            f"stderr={completed.stderr[-3000:]}"
        ) from error


def verify_reference_integrity():
    expected = pathlib.Path(
        "/opt/reference-integrity/source-hashes.sha256"
    ).read_text().splitlines()
    failures = []
    for line in expected:
        digest, relative = line.split("  ", 1)
        if relative.startswith("reference/host-source/"):
            path = PRISTINE_HOST / relative.removeprefix("reference/host-source/")
        elif relative.startswith("reference/donor-source/"):
            path = pathlib.Path("/opt/reference-donor") / relative.removeprefix(
                "reference/donor-source/"
            )
        else:
            failures.append(relative)
            continue
        completed = subprocess.run(
            ["sha256sum", str(path)], capture_output=True, text=True, check=False
        )
        if completed.returncode or completed.stdout.split()[0] != digest:
            failures.append(relative)
    lock_path = pathlib.Path("/opt/reference-runner/source-lock.json")
    try:
        source_lock = json.loads(lock_path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        failures.append(f"source-lock.json: {error}")
        source_lock = {}
    expected_lock_values = {
        "host.commit": LOCKED_HOST_COMMIT,
        "host.tree": LOCKED_HOST_TREE,
        "donor.commit": LOCKED_DONOR_COMMIT,
        "donor.tree": LOCKED_DONOR_TREE,
        "reference_wheel.filename": LOCKED_SHAP_WHEEL,
        "reference_wheel.sha256": LOCKED_SHAP_WHEEL_SHA256,
        "reference_wheel.built_from_donor_commit": LOCKED_DONOR_COMMIT,
    }
    for dotted_key, expected_value in expected_lock_values.items():
        value = source_lock
        for key in dotted_key.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value != expected_value:
            failures.append(f"source-lock identity mismatch: {dotted_key}")

    wheel_path = pathlib.Path("/opt/reference-wheels") / LOCKED_SHAP_WHEEL
    try:
        wheel_digest = hashlib.sha256(wheel_path.read_bytes()).hexdigest()
    except OSError as error:
        failures.append(f"reference wheel: {error}")
        wheel_digest = None
    if wheel_digest != LOCKED_SHAP_WHEEL_SHA256:
        failures.append("reference wheel SHA-256 mismatch")
    identity = {
        "host_commit": source_lock.get("host", {}).get("commit"),
        "host_tree": source_lock.get("host", {}).get("tree"),
        "donor_commit": source_lock.get("donor", {}).get("commit"),
        "donor_tree": source_lock.get("donor", {}).get("tree"),
        "reference_wheel": wheel_path.name,
        "reference_wheel_sha256": wheel_digest,
    }
    return failures, identity


def source_scan():
    forbidden = re.compile(
        r"(?:\bimport\s+shap\b|\bfrom\s+shap\b|shap\.TreeExplainer|"
        r"tree_shap\.h|dense_tree_shap|/opt/reference|/tests)",
        re.IGNORECASE,
    )
    findings = []
    changed = []
    for path in sorted(TESTBED.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(TESTBED)
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        pristine = PRISTINE_HOST / relative
        candidate_bytes = path.read_bytes()
        if pristine.is_file() and candidate_bytes == pristine.read_bytes():
            continue
        # The Agent image receives extension modules copied from the exact
        # locked wheel. They are runtime scaffolding, not Agent changes, and
        # materialization never overlays binary files into the candidate.
        if path.suffix == ".so" and not pristine.exists():
            continue
        changed.append(str(relative))
        if path.stat().st_size > 700_000:
            findings.append(f"oversized changed file: {relative}")
            continue
        if path.suffix == ".so" or b"\x00" in candidate_bytes:
            findings.append(f"changed binary file is not permitted: {relative}")
            continue
        text = candidate_bytes.decode("utf-8", errors="replace")
        match = forbidden.search(text)
        if match:
            findings.append(f"forbidden donor/verifier reference in {relative}: {match.group(0)!r}")
    required = [
        "sklearn/inspection/_tree_shap.py",
        "sklearn/inspection/__init__.py",
        "sklearn/inspection/tests/test_tree_shap.py",
    ]
    for relative in required:
        if relative not in changed:
            findings.append(f"required source integration is missing: {relative}")
    return findings, changed


def materialize_candidate():
    completed = subprocess.run(
        [
            sys.executable,
            "/opt/candidate-tools/materialize_candidate.py",
            "--testbed",
            str(TESTBED),
            "--pristine",
            str(PRISTINE_HOST),
            "--output",
            str(CANDIDATE_RUNTIME),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if completed.returncode:
        raise RuntimeError(f"candidate materialization failed: {completed.stderr[-2000:]}")
    return (CANDIDATE_RUNTIME / "OVERLAY-MANIFEST.txt").read_text().splitlines()


def remove_reference_materials():
    def remove_tree(path):
        # Some rootless overlay filesystems expose directory-entry deletion a
        # fraction late. Retry an explicit, fixed path and still fail closed if
        # any private material remains.
        for attempt in range(8):
            try:
                shutil.rmtree(path)
            except FileNotFoundError:
                return
            except OSError:
                if attempt == 7:
                    raise
                time.sleep(0.15 * (attempt + 1))
            else:
                return

    for path in (
        pathlib.Path("/opt/reference-venv"),
        pathlib.Path("/opt/reference-donor"),
        pathlib.Path("/opt/reference-runner"),
        pathlib.Path("/opt/reference-wheels"),
        PRISTINE_HOST,
        pathlib.Path("/opt/wheels"),
        pathlib.Path("/opt/candidate-tools"),
        pathlib.Path("/opt/reference-integrity"),
    ):
        if path.exists():
            remove_tree(path)
    if pathlib.Path("/opt/reference-venv").exists() or pathlib.Path("/opt/reference-donor").exists():
        raise RuntimeError("reference removal failed")


def lock_candidate_files():
    for path in (TESTBED, CANDIDATE_RUNTIME):
        for command in (["chown", "-R", "root:root", str(path)], ["chmod", "-R", "a-w", str(path)]):
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
            if completed.returncode:
                raise RuntimeError(f"failed to lock {path}: {completed.stderr}")


def candidate_environment():
    home = pathlib.Path("/tmp/candidate-home")
    home.mkdir(exist_ok=True)
    os.chown(home, CANDIDATE_UID, CANDIDATE_GID)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/candidate-runner",
        "PYTHONNOUSERSITE": "1",
        "HOME": str(home),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
    }


def candidate_call(cases, env, timeout=600):
    response, stderr = run_json(
        [sys.executable, CANDIDATE_RUNNER],
        {"cases": cases},
        env=env,
        candidate=True,
        timeout=timeout,
    )
    if response.get("fatal"):
        raise RuntimeError(f"candidate fatal: {response['fatal']}\n{response.get('traceback', '')}")
    if len(response.get("results", [])) != len(cases):
        raise RuntimeError("candidate returned wrong result count")
    return response, stderr


def numeric_metrics(expected, actual):
    left = np.asarray(expected, dtype=float)
    right = np.asarray(actual, dtype=float)
    if left.shape != right.shape:
        return False, math.inf, list(left.shape), list(right.shape)
    error = float(np.max(np.abs(left - right))) if left.size else 0.0
    return bool(np.allclose(left, right, rtol=RTOL, atol=ATOL)), error, list(left.shape), list(right.shape)


def compare_case(reference, candidate):
    checks = {}
    max_errors = {}
    shapes = {}
    for field in ("values", "base_values", "predictions"):
        passed, error, expected_shape, actual_shape = numeric_metrics(
            reference[field], candidate[field]
        )
        checks[field] = passed
        max_errors[field] = error
        shapes[field] = {"expected": expected_shape, "actual": actual_shape}
    local_accuracy_ok = candidate["local_accuracy_error"] <= 2e-9
    checks["local_accuracy"] = local_accuracy_ok
    values = np.asarray(candidate["values"], dtype=float)
    unused = sorted(set(range(reference["n_features"])) - set(reference["used_features"]))
    unused_error = 0.0
    if unused:
        unused_values = values[:, unused] if values.ndim == 2 else values[:, unused, :]
        unused_error = float(np.max(np.abs(unused_values)))
    checks["unused_features_exact_zero"] = unused_error == 0.0
    return all(checks.values()), {
        "checks": checks,
        "max_abs_errors": max_errors,
        "shapes": shapes,
        "candidate_local_accuracy_error": candidate["local_accuracy_error"],
        "unused_features": unused,
        "unused_feature_max_abs": unused_error,
    }


def scientific_invariants(single, duplicated):
    if not single.get("ok") or not duplicated.get("ok"):
        return False, {"error": "candidate failed an invariant case"}
    first = single["result"]
    second = duplicated["result"]
    phi1 = np.asarray(first["values"], dtype=float)
    phi2 = np.asarray(second["values"], dtype=float)
    base1 = np.asarray(first["base_values"], dtype=float)
    base2 = np.asarray(second["base_values"], dtype=float)
    pred1 = np.asarray(first["predictions"], dtype=float)
    pred2 = np.asarray(second["predictions"], dtype=float)
    # Same init raw value; duplicating the one boosting tree doubles only the
    # tree attribution and its deviation from the base value.
    phi_error = float(np.max(np.abs(phi2 - 2.0 * phi1)))
    base_error = float(np.max(np.abs(base2 - base1)))
    prediction_error = float(np.max(np.abs((pred2 - base2) - 2.0 * (pred1 - base1))))
    return max(phi_error, base_error, prediction_error) <= 2e-9, {
        "duplicate_tree_phi_error": phi_error,
        "duplicate_tree_base_error": base_error,
        "duplicate_tree_prediction_error": prediction_error,
    }


def api_and_regression(env, response):
    isolation = response.get("isolation_checks", {})
    contract = response.get("contract_checks", [])
    isolation_ok = len(isolation) == 7 and all(isolation.values())
    contract_ok = len(contract) == 8 and all(item.get("rejected") for item in contract)
    regression_env = dict(env)
    regression_env["PYTHONPATH"] = str(CANDIDATE_RUNTIME)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--confcutdir=/tmp",
            str(CANDIDATE_RUNTIME / "sklearn/inspection/tests/test_tree_shap.py"),
            str(CANDIDATE_RUNTIME / "sklearn/tree/tests/test_tree.py"),
            "--basetemp=/tmp/candidate-home/pytest-tmp",
        ],
        cwd="/tmp",
        env=regression_env,
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
        preexec_fn=demote if os.getuid() == 0 else None,
    )
    regression_ok = completed.returncode == 0
    return isolation_ok and contract_ok and regression_ok, {
        "isolation_checks": isolation,
        "contract_checks": contract,
        "regression_returncode": completed.returncode,
        "regression_stdout_tail": completed.stdout[-5000:],
        "regression_stderr_tail": completed.stderr[-3000:],
    }


def main():
    started = time.time()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    report = {
        "task": "algobridge-0026__scikit-learn__absorbs__shap",
        "tolerances": {"atol": ATOL, "rtol": RTOL},
        "points": [],
        "hard_gates": {},
    }
    reward = 0.0
    try:
        log("[1/7] Verifying locked sources and computing fresh SHAP references")
        integrity_failures, locked_identity = verify_reference_integrity()
        report["hard_gates"]["source_integrity"] = not integrity_failures
        report["source_integrity_failures"] = integrity_failures[:20]
        report["locked_identity"] = locked_identity
        if integrity_failures:
            raise RuntimeError("locked reference source integrity failed")
        all_cases = hidden_cases() + invariant_cases()
        reference_env = {
            "PATH": "/opt/reference-venv/bin:/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": "/opt/reference-runner",
            "PYTHONNOUSERSITE": "1",
            "HOME": "/tmp/reference-home",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
        reference, reference_stderr = run_json(
            [REFERENCE_PYTHON, REFERENCE_RUNNER],
            {"cases": all_cases},
            env=reference_env,
            timeout=600,
        )
        provenance = reference.get("provenance", {})
        reference_ok = (
            provenance.get("sklearn_version") == "1.10.dev0"
            and provenance.get("sklearn_file", "").startswith("/opt/reference-venv/")
            and provenance.get("shap_version") == "0.52.1.dev42"
            and provenance.get("shap_file", "").startswith("/opt/reference-venv/")
        )
        report["hard_gates"]["locked_reference_pipeline"] = reference_ok
        report["reference_provenance"] = provenance
        report["reference_stderr"] = reference_stderr[-2000:]
        if not reference_ok or len(reference.get("results", [])) != len(all_cases):
            raise RuntimeError("locked reference provenance failed")

        log("[2/7] Scanning candidate changes and materializing isolated sklearn")
        findings, changed = source_scan()
        report["source_scan"] = {"passed": not findings, "findings": findings, "changed_files": changed}
        report["hard_gates"]["clean_room_source_scan"] = not findings
        if findings:
            raise RuntimeError("source isolation scan failed")
        manifest = materialize_candidate()
        report["candidate_overlay_manifest"] = manifest

        log("[3/7] Destroying private SHAP, reference, pristine, and wheel materials")
        remove_reference_materials()
        lock_candidate_files()
        env = candidate_environment()

        log("[4/7] Running candidate as unprivileged UID 10001")
        candidate, candidate_stderr = candidate_call(all_cases, env, timeout=600)
        report["candidate_stderr"] = candidate_stderr[-3000:]

        log("[5/7] Comparing 13 hidden model fixtures")
        point_results = []
        for spec, expected, actual_item in zip(
            hidden_cases(), reference["results"][: len(hidden_cases())], candidate["results"][: len(hidden_cases())], strict=True
        ):
            if not actual_item.get("ok"):
                passed, details = False, {"candidate_error": actual_item.get("error")}
            else:
                passed, details = compare_case(expected, actual_item["result"])
            point_results.append({"name": spec["name"], "passed": passed, "details": details})

        log("[6/7] Checking linearity, API, isolation, and host regressions")
        invariant_actual = candidate["results"][len(hidden_cases()) :]
        invariant_ok, invariant_details = scientific_invariants(*invariant_actual)
        point_results.append({"name": "scientific_invariants", "passed": invariant_ok, "details": invariant_details})
        gate_ok, gate_details = api_and_regression(env, candidate)
        point_results.append({"name": "api_isolation_and_host_regression", "passed": gate_ok, "details": gate_details})
        report["points"] = point_results
        report["hard_gates"]["candidate_isolation"] = all(candidate.get("isolation_checks", {}).values())
        report["hard_gates"]["host_regression"] = gate_details["regression_returncode"] == 0

        passed_count = sum(point["passed"] for point in point_results)
        hard_gates_ok = all(report["hard_gates"].values())
        reward = passed_count / len(POINT_NAMES) if hard_gates_ok else 0.0
        report["summary"] = {
            "passed": passed_count,
            "total": len(POINT_NAMES),
            "hard_gates_ok": hard_gates_ok,
            "reward": reward,
        }
        log(f"[7/7] Result: {passed_count}/{len(POINT_NAMES)}, Reward={reward:.12g}")
    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        report["summary"] = {"passed": 0, "total": len(POINT_NAMES), "reward": 0.0}
        log(f"Verifier fatal error: {type(error).__name__}: {error}")
        reward = 0.0
    finally:
        report["elapsed_seconds"] = time.time() - started
        (LOG_ROOT / "verifier-report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
        (LOG_ROOT / "reward.txt").write_text(f"{reward:.12g}\n")


if __name__ == "__main__":
    main()
