#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0018."""

from __future__ import annotations

import copy
import hashlib
import io
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

from cases import hidden_cases


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-prody-source")
MODULE = Path("alphafold/common/normal_modes.py")
FORBIDDEN = re.compile(
    r"\b(prody|subprocess|ctypes|cffi|socket|requests|urllib|importlib)\b"
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


def normalized_tokens(path):
    try:
        data = path.read_bytes()
        result = []
        for token in tokenize.tokenize(io.BytesIO(data).readline):
            if token.type not in {
                tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                tokenize.COMMENT, tokenize.STRING,
            }:
                result.append(token.string)
        return result
    except (OSError, SyntaxError, tokenize.TokenError):
        return []


def donor_fragments():
    fragments = set()
    relevant = [
        DONOR / "prody/dynamics/gnm.py",
        DONOR / "prody/dynamics/anm.py",
        DONOR / "prody/dynamics/analysis.py",
    ]
    for path in relevant:
        tokens = normalized_tokens(path)
        for size in (64, 96):
            fragments.update(
                tuple(tokens[index:index + size])
                for index in range(max(0, len(tokens) - size + 1))
            )
    return fragments


def source_policy():
    candidate = manifest(TESTBED)
    pristine = manifest(PRISTINE)
    missing = sorted(set(pristine) - set(candidate))
    changed = sorted(
        name for name in set(pristine) & set(candidate)
        if pristine[name] != candidate[name]
    )
    added = sorted(set(candidate) - set(pristine))
    if missing:
        return False, f"host files removed: {missing[:4]}"
    if changed:
        return False, f"locked host files changed: {changed[:4]}"
    if set(added) != {str(MODULE)}:
        return False, f"unexpected added files: {added[:4]}"
    module_path = TESTBED / MODULE
    if not module_path.is_file():
        return False, "missing alphafold/common/normal_modes.py"
    if module_path.stat().st_size > 100_000:
        return False, "candidate module exceeds 100000 bytes"
    try:
        text = module_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "candidate module is not UTF-8 text"
    if FORBIDDEN.search(text):
        return False, "candidate contains a forbidden dependency or execution primitive"
    tokens = normalized_tokens(module_path)
    fragments = donor_fragments()
    for size in (96, 64):
        if any(tuple(tokens[index:index + size]) in fragments
               for index in range(max(0, len(tokens) - size + 1))):
            return False, f"candidate contains a normalized donor fragment ({size} tokens)"
    return True, {
        "added": added,
        "module_sha256": sha256(module_path),
        "module_bytes": module_path.stat().st_size,
        "donor_fragment_scan": "pass",
    }


def prepare_cases():
    sys.path.insert(0, "/opt/pristine-host")
    sys.path.insert(0, "/opt/parser-compat")
    from alphafold.common import protein as af_protein

    cases = hidden_cases()
    for case in cases:
        if case["format"] == "mmcif":
            parsed = af_protein.from_pdb_string(case["structure"])
            case["structure"] = af_protein.to_mmcif(
                parsed, file_id="HIDDEN", model_type="Multimer"
            )
    return cases


def invalid_cases(valid_case):
    result = []
    for name, changes in (
        ("invalid_cutoff", {"cutoff": 3.5}),
        ("invalid_model", {"model": "pca"}),
        ("invalid_n_modes", {"n_modes": 0}),
        ("empty_selection", {"plddt_threshold": 101.0}),
    ):
        case = copy.deepcopy(valid_case)
        case["name"] = name
        case["arguments"].update(changes)
        result.append(case)
    return result


def run_json(command, payload, env=None, timeout=240):
    completed = subprocess.run(
        command, input=json.dumps(payload), text=True, capture_output=True,
        env=env, timeout=timeout, check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stderr[-1800:]}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON output: {completed.stdout[-1800:]}") from exc


def array(value, shape=None):
    result = np.asarray(value, dtype=float)
    if shape is not None and result.shape != shape:
        raise ValueError(f"expected shape {shape}, got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError("non-finite numeric output")
    return result


def derived_statistics(model_name, modes, eigenvalues, n_residues):
    covariance = (modes * (1.0 / eigenvalues)[None, :]) @ modes.T
    if model_name == "gnm":
        residue_covariance = covariance
    else:
        blocks = covariance.reshape(n_residues, 3, n_residues, 3)
        residue_covariance = np.trace(blocks, axis1=1, axis2=3)
    msf = np.diag(residue_covariance)
    denominator = np.sqrt(np.outer(msf, msf))
    correlation = np.divide(
        residue_covariance, denominator,
        out=np.zeros_like(residue_covariance), where=denominator > 0,
    )
    return msf, correlation


def compare_case(expected, observed):
    reasons = []
    metrics = {}
    try:
        if observed["model"] != expected["model"]:
            reasons.append("model")
        if observed["residue_mapping"] != expected["residue_mapping"]:
            reasons.append("residue_mapping")
        n_residues = len(expected["residue_mapping"])
        dof = n_residues if expected["model"] == "gnm" else 3 * n_residues
        expected_network = array(expected["network_matrix"], (dof, dof))
        network = array(observed["network_matrix"], (dof, dof))
        metrics["network_max_abs"] = float(np.max(np.abs(network - expected_network)))
        if not np.allclose(network, expected_network, atol=2e-10, rtol=2e-10):
            reasons.append("network_matrix")
        if int(observed["zero_mode_count"]) != int(expected["zero_mode_count"]):
            reasons.append("zero_mode_count")

        expected_eigenvalues = array(expected["eigenvalues"])
        eigenvalues = array(observed["eigenvalues"], expected_eigenvalues.shape)
        metrics["eigenvalue_max_abs"] = float(
            np.max(np.abs(eigenvalues - expected_eigenvalues))
        )
        if not np.allclose(
            eigenvalues, expected_eigenvalues, atol=2e-7, rtol=2e-7
        ):
            reasons.append("eigenvalues")
        n_modes = len(expected_eigenvalues)
        expected_modes = array(expected["modes"], (dof, n_modes))
        modes = array(observed["modes"], (dof, n_modes))
        projector_error = float(np.max(np.abs(
            modes @ modes.T - expected_modes @ expected_modes.T
        )))
        metrics["projector_max_abs"] = projector_error
        if projector_error > 5e-6:
            reasons.append("mode_subspace")

        expected_msf = array(expected["msf"], (n_residues,))
        msf = array(observed["msf"], (n_residues,))
        metrics["msf_max_abs"] = float(np.max(np.abs(msf - expected_msf)))
        if not np.allclose(msf, expected_msf, atol=5e-6, rtol=5e-6):
            reasons.append("msf")
        expected_correlation = array(
            expected["cross_correlation"], (n_residues, n_residues)
        )
        correlation = array(
            observed["cross_correlation"], (n_residues, n_residues)
        )
        metrics["correlation_max_abs"] = float(
            np.max(np.abs(correlation - expected_correlation))
        )
        if not np.allclose(
            correlation, expected_correlation, atol=5e-6, rtol=5e-6
        ):
            reasons.append("cross_correlation")

        if not np.allclose(network, network.T, atol=2e-10, rtol=0):
            reasons.append("symmetric_network_invariant")
        if expected["model"] == "gnm":
            if not np.allclose(network.sum(axis=1), 0.0, atol=2e-10):
                reasons.append("kirchhoff_row_sum_invariant")
        else:
            translations = np.zeros((dof, 3))
            for coordinate in range(3):
                translations[coordinate::3, coordinate] = 1.0
            if not np.allclose(network @ translations, 0.0, atol=2e-9):
                reasons.append("translation_zero_mode_invariant")
        full_eigenvalues = np.linalg.eigvalsh(network)
        if int(np.sum(full_eigenvalues < 1e-6)) != int(observed["zero_mode_count"]):
            reasons.append("zero_mode_threshold_invariant")
        if np.any(eigenvalues < 1e-6) or np.any(np.diff(eigenvalues) < -1e-10):
            reasons.append("positive_sorted_modes_invariant")
        if not np.allclose(modes.T @ modes, np.eye(n_modes), atol=5e-7):
            reasons.append("orthonormal_modes_invariant")
        residual = network @ modes - modes * eigenvalues[None, :]
        if np.max(np.abs(residual)) > 2e-6:
            reasons.append("eigenpair_residual_invariant")
        internal_msf, internal_correlation = derived_statistics(
            expected["model"], modes, eigenvalues, n_residues
        )
        if not np.allclose(msf, internal_msf, atol=2e-7, rtol=2e-7):
            reasons.append("msf_consistency_invariant")
        if not np.allclose(
            correlation, internal_correlation, atol=2e-7, rtol=2e-7
        ):
            reasons.append("correlation_consistency_invariant")
        if np.any(msf < -1e-12):
            reasons.append("nonnegative_msf_invariant")
        if not np.allclose(correlation, correlation.T, atol=2e-9):
            reasons.append("symmetric_correlation_invariant")
        positive = msf > 1e-14
        if not np.allclose(np.diag(correlation)[positive], 1.0, atol=2e-9):
            reasons.append("correlation_diagonal_invariant")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        reasons.append(f"protocol:{type(exc).__name__}")
    return not reasons, sorted(set(reasons)), metrics


def check_rigid_invariance(observed_by_name):
    failures = []
    pairs = (
        ("gnm_curved_chain", "gnm_translated", 2e-8),
        ("anm_helix", "anm_rotated", 2e-3),
    )
    for first, second, tolerance in pairs:
        left = observed_by_name.get(first, {}).get("result")
        right = observed_by_name.get(second, {}).get("result")
        if left is None or right is None:
            failures.append(f"{first}/{second}:missing")
            continue
        for key in ("eigenvalues", "msf", "cross_correlation"):
            if not np.allclose(array(left[key]), array(right[key]),
                               atol=tolerance, rtol=tolerance):
                failures.append(f"{first}/{second}:{key}")
    return failures


def main():
    cases = prepare_cases()
    invalid = invalid_cases(cases[0])
    report = {
        "task": "ALGOBRIDGE-0018",
        "reference": "locked AlphaFold parser to ProDy 2.6.1 commit 7969f497",
        "total": len(cases),
        "hard_gates": {},
    }
    try:
        reference = run_json(
            [sys.executable, "/opt/reference-runner/reference_runner.py"],
            {"cases": cases},
            env={
                **os.environ,
                "PYTHONPATH": "/opt/reference-runtime:/opt/pristine-host:/opt/parser-compat:/tests",
                "PYTHONNOUSERSITE": "1",
            },
        )
    except Exception as exc:
        fail(f"reference runner failed: {exc}", report)
    report["hard_gates"]["locked_reference"] = "pass"

    policy_ok, policy_detail = source_policy()
    if not policy_ok:
        fail(f"source policy failed: {policy_detail}", report)
    report["hard_gates"]["source_policy"] = policy_detail

    subprocess.run(["chown", "-R", "root:root", str(TESTBED)], check=True)
    subprocess.run(["chmod", "-R", "a+rX", str(TESTBED)], check=True)
    subprocess.run(["chmod", "-R", "a-w", str(TESTBED)], check=True)
    for path in (
        "/opt/reference-runtime", "/opt/reference-prody-source",
        "/opt/reference-runner", "/opt/source-archives", "/opt/wheels",
        "/opt/pristine-host",
    ):
        shutil.rmtree(path, ignore_errors=True)
    isolation_targets = [
        "/opt/reference-runtime", "/opt/reference-prody-source",
        "/opt/reference-runner", "/opt/source-archives", "/opt/wheels",
        "/opt/pristine-host",
    ]
    if any(Path(path).exists() for path in isolation_targets):
        fail("reference isolation cleanup failed", report)
    report["hard_gates"]["reference_removed_before_candidate"] = "pass"

    home = Path("/tmp/candidate-home")
    home.mkdir(mode=0o700, exist_ok=True)
    shutil.chown(home, user=10001, group=10001)
    command = [
        "runuser", "-u", "candidate", "--", "env", "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp/candidate-home",
        "PYTHONNOUSERSITE=1", "PYTHONPATH=/testbed:/opt/parser-compat",
        "OPENBLAS_NUM_THREADS=1", "OMP_NUM_THREADS=1", sys.executable,
        "/opt/candidate-runner/candidate_runner.py",
    ]
    try:
        candidate = run_json(command, {"cases": cases + invalid})
    except Exception as exc:
        fail(f"candidate runner failed: {exc}", report)
    report["hard_gates"]["candidate_protocol"] = "pass"

    observed_by_name = {item["name"]: item for item in candidate["cases"]}
    invalid_failures = []
    for case in invalid:
        observed = observed_by_name.get(case["name"], {})
        if observed.get("error") not in {"TypeError", "ValueError"}:
            invalid_failures.append(case["name"])
    if invalid_failures:
        fail(f"invalid-input contract failed: {invalid_failures}", report)
    report["hard_gates"]["invalid_input_rejection"] = "pass"

    rigid_failures = check_rigid_invariance(observed_by_name)
    if rigid_failures:
        fail(f"rigid-transform invariant failed: {rigid_failures}", report)
    report["hard_gates"]["rigid_transform_invariance"] = "pass"

    expected_by_name = {item["name"]: item for item in reference["cases"]}
    results = []
    passed = 0
    for case in cases:
        name = case["name"]
        expected_item = expected_by_name.get(name, {})
        observed_item = observed_by_name.get(name, {})
        if "result" not in expected_item:
            fail(f"reference omitted result for {name}", report)
        if "result" not in observed_item:
            ok, reasons, metrics = (
                False, [f"candidate_error:{observed_item.get('error', 'missing')}"], {}
            )
        else:
            ok, reasons, metrics = compare_case(
                expected_item["result"], observed_item["result"]
            )
        passed += int(ok)
        results.append({
            "name": name, "passed": ok, "reasons": reasons, "metrics": metrics,
        })

    reward = passed / len(cases)
    report.update({
        "status": "completed", "passed": passed,
        "failed": len(cases) - passed, "cases": results,
    })
    write_report(report, reward)


if __name__ == "__main__":
    main()
