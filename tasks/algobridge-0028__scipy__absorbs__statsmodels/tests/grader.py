#!/usr/bin/env python3
"""Separate differential verifier for ALGOBRIDGE-0028."""

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
import time

import numpy as np

from cases import POINT_NAMES, hidden_cases


TESTBED = Path("/testbed")
LOG_ROOT = Path("/logs/verifier")
REFERENCE_PYTHON = "/opt/reference-venv/bin/python"
REFERENCE_RUNNER = "/opt/reference-runner/reference_runner.py"
CANDIDATE_RUNNER = "/opt/candidate-runner/candidate_runner.py"
PRISTINE_HOST = Path("/opt/pristine-host")
CANDIDATE_RUNTIME = Path("/opt/candidate-runtime")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
SOURCE_HASHES = Path("/opt/reference-runner/source-hashes.sha256")
SOURCE_LINKS = Path("/opt/reference-runner/source-links.txt")


def log(message):
    print(message, flush=True)


def _demote():
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def run_json(command, payload, *, env=None, candidate=False, timeout=180):
    completed = subprocess.run(
        command,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=_demote if candidate and os.getuid() == 0 else None,
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
            f"runner returned non-JSON: {completed.stdout[-3000:]}\n"
            f"stderr={completed.stderr[-3000:]}"
        ) from error


def source_scan():
    forbidden = re.compile(
        r"(^|[^A-Za-z0-9_])(statsmodels|/opt/reference|/tests|reference_runner)"
        r"([^A-Za-z0-9_]|$)",
        re.IGNORECASE,
    )
    findings = []
    changed = []
    locked_hashes = {}
    for line in SOURCE_HASHES.read_text().splitlines():
        digest, relative = line.split("  ", 1)
        locked_hashes[relative.removeprefix("./")] = digest
    locked_links = {}
    for line in SOURCE_LINKS.read_text().splitlines():
        relative, target = line.split("\t", 1)
        locked_links[relative] = target

    for relative in locked_hashes:
        if not (TESTBED / relative).is_file():
            findings.append(f"deleted locked file: {relative}")
    for relative, target in locked_links.items():
        path = TESTBED / relative
        if not path.is_symlink() or os.readlink(path) != target:
            findings.append(f"changed locked symlink: {relative}")

    for path in sorted(TESTBED.rglob("*")):
        relative = path.relative_to(TESTBED)
        if path.is_symlink():
            if locked_links.get(str(relative)) != os.readlink(path):
                findings.append(f"untrusted symlink: {relative}")
            continue
        if not path.is_file():
            continue
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if locked_hashes.get(str(relative)) == digest:
            continue
        changed.append(str(relative))
        if path.stat().st_size > 500_000:
            findings.append(f"oversized changed file: {relative}")
        elif path.suffix == ".so" or b"\x00" in data:
            findings.append(f"changed binary file is not permitted: {relative}")
        else:
            text = data.decode("utf-8", errors="replace")
            pristine = PRISTINE_HOST / relative
            if pristine.is_file():
                original = pristine.read_text(errors="replace").splitlines()
                current = text.splitlines()
                text = "\n".join(
                    line[1:]
                    for line in difflib.unified_diff(original, current)
                    if line.startswith("+") and not line.startswith("+++")
                )
            match = forbidden.search(text)
            if match:
                findings.append(f"forbidden delegation in {relative}: {match.group(0)!r}")
    return findings, changed


def materialize_candidate():
    completed = subprocess.run(
        [
            sys.executable,
            "/opt/candidate-tools/materialize_candidate.py",
            "--testbed", str(TESTBED),
            "--pristine", str(PRISTINE_HOST),
            "--output", str(CANDIDATE_RUNTIME),
        ],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"materialization failed: {completed.stderr[-3000:]}")
    manifest = (CANDIDATE_RUNTIME / "OVERLAY-MANIFEST.txt").read_text().splitlines()
    return manifest, completed.stdout.strip()


def remove_reference_materials():
    for path in (
        Path("/opt/reference-venv"),
        Path("/opt/wheels"),
        Path("/opt/pristine-host"),
        Path("/opt/candidate-tools"),
    ):
        if path.exists():
            shutil.rmtree(path)
    for path in (REFERENCE_PYTHON, "/opt/wheels", "/opt/pristine-host"):
        if Path(path).exists():
            raise RuntimeError(f"reference removal failed: {path}")


def lock_candidate_files():
    for path in (TESTBED, CANDIDATE_RUNTIME):
        for command in (["chown", "-R", "root:root", str(path)],
                        ["chmod", "-R", "a-w", str(path)]):
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError(f"failed to lock {path}: {completed.stderr}")


def isolation_probe(env):
    code = r'''
import importlib.util
import json
import os
import pathlib
checks = {
    "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
    "reference_runner_unreadable": not os.access("/opt/reference-runner/reference_runner.py", os.R_OK),
    "reference_venv_removed": not pathlib.Path("/opt/reference-venv").exists(),
    "pristine_host_removed": not pathlib.Path("/opt/pristine-host").exists(),
    "wheelhouse_removed": not pathlib.Path("/opt/wheels").exists(),
    "candidate_tools_removed": not pathlib.Path("/opt/candidate-tools").exists(),
    "statsmodels_unavailable": importlib.util.find_spec("statsmodels") is None,
}
print(json.dumps(checks, sort_keys=True))
'''
    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=_demote if os.getuid() == 0 else None,
        timeout=30,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"isolation probe failed: {completed.stderr[-2000:]}")
    return json.loads(completed.stdout)


def max_error(left, right):
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.shape != right.shape:
        return math.inf
    if not np.all(np.isfinite(left)) or not np.all(np.isfinite(right)):
        return math.inf
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def close(left, right, tolerance):
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    return (
        left.shape == right.shape
        and np.all(np.isfinite(left))
        and np.all(np.isfinite(right))
        and np.allclose(left, right, rtol=tolerance, atol=tolerance)
    )


def compare_case(reference, candidate):
    field_tolerances = {
        "params": 1e-8,
        "scale": 1e-8,
        "weights": 1e-8,
        "residuals": 1e-8,
        "covariance": 1e-6,
    }
    checks = {}
    errors = {}
    for field, tolerance in field_tolerances.items():
        checks[field] = close(reference[field], candidate[field], tolerance)
        errors[field] = max_error(reference[field], candidate[field])
    for field in ("objective", "scale", "params"):
        key = f"history_{field}"
        checks[key] = close(
            reference["history"][field], candidate["history"][field], 1e-8,
        )
        errors[key] = max_error(
            reference["history"][field], candidate["history"][field],
        )
    checks["n_iter"] = reference["n_iter"] == candidate["n_iter"]
    checks["converged"] = reference["converged"] == candidate["converged"]
    return all(checks.values()), {"checks": checks, "max_abs_errors": errors}


def estimating_equation(cases, candidates):
    details = {}
    passed = True
    for spec, result in zip(cases, candidates, strict=True):
        if not result["converged"]:
            details[spec["name"]] = {"skipped": "fit reached maxiter"}
            continue
        options = spec.get("options", {})
        x = np.asarray(spec["x"], dtype=float)
        y = np.asarray(spec["y"], dtype=float)
        design = np.column_stack((np.ones(y.size), x)) if options.get("fit_intercept", True) else x
        frequencies = np.asarray(options.get("case_weights", np.ones(y.size)), dtype=int)
        design = np.repeat(design, frequencies, axis=0)
        response = np.repeat(y, frequencies)
        params = np.asarray(result["params"], dtype=float)
        scale = float(result["scale"])
        threshold = float(options.get("huber_t", 1.345))
        z = (response - design @ params) / scale
        psi = np.where(np.abs(z) <= threshold, z, threshold * np.sign(z))
        score = design.T @ psi
        normalized = float(np.linalg.norm(score) / max(1.0, np.linalg.norm(design)))
        details[spec["name"]] = {"normalized_score": normalized}
        if not np.isfinite(normalized) or normalized > 2e-5:
            passed = False
    return passed, details


def candidate_call(spec, env):
    return run_json(
        [sys.executable, CANDIDATE_RUNNER], spec,
        env=env, candidate=True,
    )[0]


def scientific_invariants(env):
    rng = np.random.default_rng(28991)
    x = rng.normal(size=(36, 3))
    beta = np.array([0.7, -1.1, 1.4])
    y = 2.2 + x @ beta + rng.normal(scale=0.12, size=36)
    base = {"name": "units_base", "x": x.tolist(), "y": y.tolist(), "options": {}}
    factor = 3.75
    scaled = {"name": "units_scaled", "x": x.tolist(), "y": (factor * y).tolist(), "options": {}}
    base_result = candidate_call(base, env)
    scaled_result = candidate_call(scaled, env)

    unit_checks = {
        "params": close(factor * np.asarray(base_result["params"]), scaled_result["params"], 2e-8),
        "scale": close(factor * base_result["scale"], scaled_result["scale"], 2e-8),
        "weights": close(base_result["weights"], scaled_result["weights"], 2e-8),
        "residuals": close(factor * np.asarray(base_result["residuals"]), scaled_result["residuals"], 2e-8),
        "covariance": close(factor**2 * np.asarray(base_result["covariance"]), scaled_result["covariance"], 2e-6),
    }
    design = np.column_stack((np.ones(y.size), x))
    ols = np.linalg.pinv(design) @ y
    ols_distance = float(np.max(np.abs(np.asarray(base_result["params"]) - ols)))
    return all(unit_checks.values()) and ols_distance < 0.035, {
        "unit_checks": unit_checks,
        "clean_ols_max_abs_distance": ols_distance,
    }


def api_and_regression(env, isolation):
    api_code = r'''
import json
import numpy as np
import scipy.stats as stats
checks = {}
checks["public_export"] = callable(stats.robust_linear_model)
x = np.arange(24.0).reshape(12, 2)
y = 1.0 + x @ np.array([0.3, -0.2]) + np.linspace(-0.1, 0.1, 12)
r = stats.robust_linear_model(x, y)
checks["result_contract"] = all(hasattr(r, name) for name in (
    "params", "scale", "weights", "covariance", "residuals", "history", "n_iter", "converged"
))
bad = 0
for kwargs in ({"huber_t": 0}, {"scale": "other"}, {"covariance": "H4"}, {"case_weights": [1] * 11 + [0]}):
    try:
        stats.robust_linear_model(x, y, **kwargs)
    except (TypeError, ValueError):
        bad += 1
checks["validation"] = bad == 4
print(json.dumps(checks, sort_keys=True))
'''
    api = subprocess.run(
        [sys.executable, "-c", api_code], capture_output=True, text=True,
        env=env, cwd="/tmp", preexec_fn=_demote if os.getuid() == 0 else None,
        timeout=60, check=False,
    )
    api_checks = json.loads(api.stdout) if api.returncode == 0 else {"error": api.stderr[-2000:]}

    regression_files = [
        str(CANDIDATE_RUNTIME / "scipy/stats/tests/test_variation.py"),
        str(CANDIDATE_RUNTIME / "scipy/stats/tests/test_rank.py"),
        str(CANDIDATE_RUNTIME / "scipy/stats/tests/test_entropy.py"),
        str(CANDIDATE_RUNTIME / "scipy/stats/tests/test_binned_statistic.py"),
    ]
    regression = subprocess.run(
        [
            sys.executable, "-m", "pytest", "-q", "--disable-warnings",
            "-p", "no:cacheprovider", "-p", "scipy.conftest", *regression_files,
        ],
        capture_output=True, text=True, env=env, cwd="/tmp",
        preexec_fn=_demote if os.getuid() == 0 else None,
        timeout=600, check=False,
    )
    passed = (
        api.returncode == 0
        and all(api_checks.values())
        and all(isolation.values())
        and regression.returncode == 0
    )
    return passed, {
        "api": api_checks,
        "isolation": isolation,
        "regression_returncode": regression.returncode,
        "regression_output": (regression.stdout + regression.stderr)[-4000:],
    }


def main():
    started = time.time()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    results = {name: {"passed": False, "details": {"reason": "not run"}} for name in POINT_NAMES}
    report = {"task": "ALGOBRIDGE-0028", "points": results}

    try:
        findings, changed = source_scan()
        report["changed_files"] = changed
        report["source_scan_findings"] = findings
        if findings:
            raise RuntimeError("source scan rejected the candidate")

        manifest, materialization_log = materialize_candidate()
        report["overlay_manifest"] = manifest
        report["materialization"] = materialization_log
        if not manifest:
            raise RuntimeError("candidate has no changed SciPy Python files")

        cases = hidden_cases()
        references = []
        for index, spec in enumerate(cases, 1):
            log(f"reference {index}/{len(cases)}: {spec['name']}")
            references.append(run_json([REFERENCE_PYTHON, REFERENCE_RUNNER], spec)[0])

        remove_reference_materials()
        lock_candidate_files()
        candidate_home = Path("/tmp/candidate-home")
        candidate_home.mkdir(exist_ok=True)
        os.chown(candidate_home, CANDIDATE_UID, CANDIDATE_GID)
        candidate_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": str(CANDIDATE_RUNTIME),
            "PYTHONNOUSERSITE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "HOME": str(candidate_home),
        }
        isolation = isolation_probe(candidate_env)
        candidates = []
        for index, spec in enumerate(cases, 1):
            log(f"candidate {index}/{len(cases)}: {spec['name']}")
            candidates.append(candidate_call(spec, candidate_env))

        for spec, reference, candidate in zip(cases, references, candidates, strict=True):
            passed, details = compare_case(reference, candidate)
            results[spec["name"]] = {"passed": passed, "details": details}

        passed, details = estimating_equation(cases, candidates)
        results["huber_estimating_equation"] = {"passed": passed, "details": details}

        passed, details = scientific_invariants(candidate_env)
        results["unit_equivariance_and_clean_ols"] = {"passed": passed, "details": details}

        passed, details = api_and_regression(candidate_env, isolation)
        results["api_isolation_and_host_regression"] = {"passed": passed, "details": details}
    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        log(report["fatal_error"])

    passed_count = sum(item["passed"] for item in results.values())
    reward = passed_count / len(POINT_NAMES)
    report.update(
        passed=passed_count,
        total=len(POINT_NAMES),
        reward=reward,
        elapsed_seconds=round(time.time() - started, 3),
    )
    (LOG_ROOT / "verifier-report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
    (LOG_ROOT / "reward.txt").write_text(f"{reward:.12g}\n")
    log(f"Reward: {reward:.12g} ({passed_count}/{len(POINT_NAMES)})")


if __name__ == "__main__":
    main()
