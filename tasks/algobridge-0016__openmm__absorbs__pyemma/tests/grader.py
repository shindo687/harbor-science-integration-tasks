#!/usr/bin/env python3
"""Separate, offline differential verifier for ALGOBRIDGE-0016."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

import numpy as np

from cases import hidden_cases


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
MODULE = Path("wrappers/python/openmm/app/markov_model.py")
INIT = Path("wrappers/python/openmm/app/__init__.py")
EXPORT = "from .markov_model import estimate_markov_model"
FORBIDDEN = re.compile(
    r"\b(pyemma|deeptime|msmtools|subprocess|ctypes|socket|requests|urllib|importlib)\b"
    r"|__import__|os\s*\.\s*system|\bpopen\s*\(|\bexec\s*\(|\beval\s*\(",
    re.IGNORECASE,
)


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


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ignored(path):
    return (
        any(part.startswith(".") for part in path.parts)
        or "__pycache__" in path.parts
        or path.suffix in {".pyc", ".pyo"}
    )


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
    candidate = manifest(TESTBED)
    pristine = manifest(PRISTINE)
    missing = sorted(set(pristine) - set(candidate))
    changed = sorted(
        name for name in set(pristine) & set(candidate)
        if pristine[name] != candidate[name]
    )
    added = sorted(set(candidate) - set(pristine))
    allowed_changed = {str(INIT)}
    allowed_added = {str(MODULE)}
    if missing:
        return False, f"host files removed: {missing[:4]}"
    if set(changed) - allowed_changed:
        return False, f"unrelated host files changed: {changed[:4]}"
    if set(added) - allowed_added:
        return False, f"unrelated files added: {added[:4]}"
    module_path = TESTBED / MODULE
    init_path = TESTBED / INIT
    if not module_path.is_file() or not init_path.is_file():
        return False, "required module or public export is missing"
    if module_path.stat().st_size > 100_000:
        return False, "candidate module exceeds 100000 bytes"
    try:
        module_text = module_path.read_text(encoding="utf-8")
        init_text = init_path.read_text(encoding="utf-8")
        pristine_init = (PRISTINE / INIT).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "candidate source is not UTF-8 text"
    if FORBIDDEN.search(module_text):
        return False, "candidate contains a forbidden dependency or execution primitive"
    if not init_text.startswith(pristine_init):
        return False, "OpenMM app __init__.py was modified beyond an appended export"
    if init_text[len(pristine_init):].strip() != EXPORT:
        return False, "OpenMM app __init__.py must append exactly the required export"
    return True, {
        "changed": changed, "added": added,
        "module_sha256": sha256(module_path),
        "module_bytes": module_path.stat().st_size,
    }


def run_json(command, payload, env=None, timeout=240):
    completed = subprocess.run(
        command, input=json.dumps(payload), text=True, capture_output=True,
        env=env, timeout=timeout, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stderr[-1500:]}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON output: {completed.stdout[-1500:]}") from exc


def as_array(value, shape=None, complex_pairs=False):
    array = np.asarray(value, dtype=float)
    if complex_pairs:
        if array.ndim != 2 or array.shape[1] != 2:
            raise ValueError("eigenvalues must be [real, imag] pairs")
        array = array[:, 0] + 1j * array[:, 1]
    if shape is not None and array.shape != shape:
        raise ValueError(f"expected shape {shape}, got {array.shape}")
    if not np.all(np.isfinite(array)):
        raise ValueError("non-finite numeric output")
    return array


def canonical_eigenvalues(matrix):
    values = [complex(value) for value in np.linalg.eigvals(matrix)]
    stationary = min(range(len(values)), key=lambda i: abs(values[i] - 1.0))
    first = values.pop(stationary)
    values.sort(key=lambda value: (-abs(value), -value.real, -value.imag))
    return np.asarray([first, *values])


def compare_timescales(expected, observed):
    if len(expected) != len(observed):
        return False
    for left, right in zip(expected, observed):
        if left is None or right is None:
            if left is not None or right is not None:
                return False
        elif not math.isclose(float(left), float(right), rel_tol=1e-6, abs_tol=1e-6):
            return False
    return True


def compare_case(case, expected, observed):
    reasons = []
    try:
        active = np.asarray(observed["active_set"], dtype=int)
        expected_active = np.asarray(expected["active_set"], dtype=int)
        if not np.array_equal(active, expected_active):
            reasons.append("active_set")
        n = len(expected_active)
        counts = as_array(observed["count_matrix"], (n, n))
        expected_counts = as_array(expected["count_matrix"], (n, n))
        if not np.array_equal(counts, expected_counts):
            reasons.append("count_matrix")
        transition = as_array(observed["transition_matrix"], (n, n))
        expected_transition = as_array(expected["transition_matrix"], (n, n))
        if not np.allclose(transition, expected_transition, atol=2e-8, rtol=2e-8):
            reasons.append("transition_matrix")
        stationary = as_array(observed["stationary_distribution"], (n,))
        expected_stationary = as_array(expected["stationary_distribution"], (n,))
        if not np.allclose(stationary, expected_stationary, atol=2e-8, rtol=2e-8):
            reasons.append("stationary_distribution")
        eigenvalues = as_array(observed["eigenvalues"], complex_pairs=True)
        expected_eigenvalues = as_array(expected["eigenvalues"], complex_pairs=True)
        if eigenvalues.shape != expected_eigenvalues.shape or not np.allclose(
            eigenvalues, expected_eigenvalues, atol=5e-7, rtol=5e-7
        ):
            reasons.append("eigenvalues")
        if not compare_timescales(expected["timescales"], observed["timescales"]):
            reasons.append("timescales")

        if np.min(transition) < -1e-12 or not np.allclose(
            transition.sum(axis=1), 1.0, atol=2e-9, rtol=0.0
        ):
            reasons.append("row_stochastic_invariant")
        if np.min(stationary) < -1e-12 or not math.isclose(
            float(stationary.sum()), 1.0, abs_tol=2e-9
        ):
            reasons.append("stationary_probability_invariant")
        if not np.allclose(stationary @ transition, stationary,
                           atol=2e-8, rtol=2e-8):
            reasons.append("left_stationary_invariant")
        if case.get("reversible", True) and not np.allclose(
            stationary[:, None] * transition,
            stationary[None, :] * transition.T,
            atol=2e-8, rtol=2e-8,
        ):
            reasons.append("detailed_balance_invariant")
        internal_eigenvalues = canonical_eigenvalues(transition)
        if eigenvalues.shape != internal_eigenvalues.shape or not np.allclose(
            eigenvalues, internal_eigenvalues, atol=5e-7, rtol=5e-7
        ):
            reasons.append("spectral_consistency_invariant")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        reasons.append(f"protocol:{type(exc).__name__}")
    return not reasons, sorted(set(reasons))


def main():
    cases = hidden_cases()
    payload = {"cases": cases}
    report = {
        "task": "ALGOBRIDGE-0016",
        "reference": "locked PyEMMA 2.5.12+6.g3327f28b estimate_markov_model",
        "total": len(cases),
        "hard_gates": {},
    }

    try:
        reference = run_json(
            [sys.executable, "/opt/reference-runner/reference_runner.py"], payload,
            env={**os.environ, "PYTHONPATH": "/opt/reference-runtime",
                 "PYTHONNOUSERSITE": "1"},
        )
    except Exception as exc:
        fail(f"reference runner failed: {exc}", report)
    report["hard_gates"]["locked_reference"] = "pass"

    policy_ok, policy_detail = source_policy()
    if not policy_ok:
        fail(f"source policy failed: {policy_detail}", report)
    report["hard_gates"]["source_policy"] = policy_detail

    try:
        subprocess.run(
            [sys.executable, "/opt/candidate-tools/materialize_candidate.py"],
            check=True, capture_output=True, text=True, timeout=60,
        )
    except Exception as exc:
        fail(f"candidate materialization failed: {exc}", report)

    for path in (
        "/opt/reference-runtime", "/opt/reference-pyemma-source",
        "/opt/reference-runner", "/opt/source-archives", "/opt/wheels",
        "/opt/pristine-host", "/opt/candidate-tools",
    ):
        shutil.rmtree(path, ignore_errors=True)
    isolation_targets = [
        "/opt/reference-runtime", "/opt/reference-pyemma-source",
        "/opt/reference-runner", "/opt/source-archives", "/opt/wheels",
    ]
    if any(Path(path).exists() for path in isolation_targets):
        fail("reference isolation cleanup failed", report)
    report["hard_gates"]["reference_removed_before_candidate"] = "pass"

    home = Path("/tmp/candidate-home")
    home.mkdir(mode=0o700, exist_ok=True)
    shutil.chown(home, user=10001, group=10001)
    command = [
        "runuser", "-u", "candidate", "--", "env", "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin",
        "HOME=/tmp/candidate-home", "PYTHONNOUSERSITE=1",
        "PYTHONPATH=/opt/candidate-runtime", "OPENBLAS_NUM_THREADS=1",
        "OMP_NUM_THREADS=1", sys.executable,
        "/opt/candidate-runner/candidate_runner.py",
    ]
    try:
        candidate = run_json(command, payload)
    except Exception as exc:
        fail(f"candidate runner failed: {exc}", report)
    report["hard_gates"]["candidate_protocol"] = "pass"

    expected_by_name = {item["name"]: item for item in reference["cases"]}
    observed_by_name = {item["name"]: item for item in candidate["cases"]}
    results = []
    passed = 0
    for case in cases:
        name = case["name"]
        expected_item = expected_by_name.get(name, {})
        observed_item = observed_by_name.get(name, {})
        if "result" not in expected_item:
            fail(f"reference omitted result for {name}", report)
        if "result" not in observed_item:
            ok, reasons = False, [f"candidate_error:{observed_item.get('error', 'missing')}" ]
        else:
            ok, reasons = compare_case(
                case, expected_item["result"], observed_item["result"]
            )
        passed += int(ok)
        results.append({"name": name, "passed": ok, "reasons": reasons})

    reward = passed / len(cases)
    report.update({
        "status": "completed", "passed": passed, "failed": len(cases) - passed,
        "cases": results,
    })
    write_report(report, reward)


if __name__ == "__main__":
    main()
