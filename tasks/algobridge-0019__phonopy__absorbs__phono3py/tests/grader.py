#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0019."""

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
from model import predict_forces, symmetry_operations


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-phono3py-source")
MODULE = Path("phonopy/harmonic/third_order.py")
FORBIDDEN = re.compile(
    r"\b(phono3py|symfc|phonors|subprocess|ctypes|cffi|socket|requests|urllib|importlib)\b"
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
        output = []
        for token in tokenize.tokenize(io.BytesIO(path.read_bytes()).readline):
            if token.type not in {
                tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                tokenize.COMMENT, tokenize.STRING,
            }:
                output.append(token.string)
        return output
    except (OSError, SyntaxError, tokenize.TokenError):
        return []


def donor_fragments():
    fragments = set()
    relevant = [
        DONOR / "phono3py/interface/fc_calculator.py",
        DONOR / "phono3py/phonon3/fc3.py",
        DONOR / "phono3py/api_phono3py.py",
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
    path = TESTBED / MODULE
    if not path.is_file():
        return False, "missing phonopy/harmonic/third_order.py"
    if path.stat().st_size > 100_000:
        return False, "candidate module exceeds 100000 bytes"
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "candidate module is not UTF-8 text"
    if FORBIDDEN.search(text):
        return False, "candidate contains a forbidden dependency or execution primitive"
    tokens = normalized_tokens(path)
    fragments = donor_fragments()
    for size in (96, 64):
        if any(tuple(tokens[index:index + size]) in fragments
               for index in range(max(0, len(tokens) - size + 1))):
            return False, f"candidate contains a normalized donor fragment ({size} tokens)"
    return True, {
        "added": added,
        "module_sha256": sha256(path),
        "module_bytes": path.stat().st_size,
        "donor_fragment_scan": "pass",
    }


def invalid_cases(valid):
    cases = []

    one_atom = copy.deepcopy(valid)
    one_atom["name"] = "invalid_one_atom"
    one_atom["cell"]["symbols"] = one_atom["cell"]["symbols"][:1]
    one_atom["cell"]["scaled_positions"] = one_atom["cell"]["scaled_positions"][:1]
    one_atom["displacements"] = np.asarray(one_atom["displacements"])[:, :1].tolist()
    one_atom["forces"] = np.asarray(one_atom["forces"])[:, :1].tolist()
    cases.append(one_atom)

    mismatch = copy.deepcopy(valid)
    mismatch["name"] = "invalid_shape_mismatch"
    mismatch["forces"] = mismatch["forces"][:-1]
    cases.append(mismatch)

    nonfinite = copy.deepcopy(valid)
    nonfinite["name"] = "invalid_nonfinite"
    nonfinite["displacements"][0][0][0] = float("nan")
    cases.append(nonfinite)

    wrong_flag = copy.deepcopy(valid)
    wrong_flag["name"] = "invalid_symmetry_flag"
    wrong_flag["arguments"]["is_symmetry"] = "yes"
    cases.append(wrong_flag)

    wrong_tolerance = copy.deepcopy(valid)
    wrong_tolerance["name"] = "invalid_symprec"
    wrong_tolerance["arguments"]["symprec"] = 0.0
    cases.append(wrong_tolerance)
    return cases


def run_json(command, payload, env=None, timeout=300):
    completed = subprocess.run(
        command,
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        env=env,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stderr[-2000:]}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON output: {completed.stdout[-2000:]}") from exc


def array(value, shape=None):
    result = np.asarray(value, dtype=float)
    if shape is not None and result.shape != shape:
        raise ValueError(f"expected shape {shape}, got {result.shape}")
    if not np.all(np.isfinite(result)):
        raise ValueError("non-finite numeric output")
    return result


def close(left, right, atol, rtol=None):
    return np.allclose(left, right, atol=atol, rtol=atol if rtol is None else rtol)


def symmetry_force_error(item, fc2, fc3, predicted):
    if not item["arguments"]["is_symmetry"]:
        return 0.0
    from phonopy.structure.atoms import PhonopyAtoms

    specification = item["cell"]
    cell = PhonopyAtoms(
        symbols=specification["symbols"],
        cell=specification["cell"],
        scaled_positions=specification["scaled_positions"],
    )
    rotations, permutations_ = symmetry_operations(
        cell, True, item["arguments"]["symprec"]
    )
    displacements = np.asarray(item["displacements"], dtype=float)[:2]
    source_prediction = predicted[:2]
    maximum = 0.0
    for rotation, permutation in zip(rotations, permutations_, strict=True):
        transformed_u = np.zeros_like(displacements)
        transformed_expected = np.zeros_like(source_prediction)
        for source, target in enumerate(permutation):
            transformed_u[:, target] = displacements[:, source] @ rotation.T
            transformed_expected[:, target] = source_prediction[:, source] @ rotation.T
        transformed_observed = predict_forces(transformed_u, fc2, fc3)
        maximum = max(
            maximum,
            float(np.max(np.abs(transformed_observed - transformed_expected))),
        )
    return maximum


def compare_case(item, expected, observed):
    reasons = []
    metrics = {}
    try:
        n_atoms = len(item["cell"]["symbols"])
        n_snapshots = len(item["displacements"])
        fc2_shape = (n_atoms, n_atoms, 3, 3)
        fc3_shape = (n_atoms, n_atoms, n_atoms, 3, 3, 3)
        force_shape = (n_snapshots, n_atoms, 3)
        expected_fc2 = array(expected["fc2"], fc2_shape)
        expected_fc3 = array(expected["fc3"], fc3_shape)
        fc2 = array(observed["fc2"], fc2_shape)
        fc3 = array(observed["fc3"], fc3_shape)
        expected_predicted = array(expected["predicted_forces"], force_shape)
        predicted = array(observed["predicted_forces"], force_shape)

        metrics["fc2_max_abs"] = float(np.max(np.abs(fc2 - expected_fc2)))
        metrics["fc3_max_abs"] = float(np.max(np.abs(fc3 - expected_fc3)))
        metrics["predicted_force_max_abs"] = float(
            np.max(np.abs(predicted - expected_predicted))
        )
        if not close(fc2, expected_fc2, 2e-7):
            reasons.append("fc2")
        if not close(fc3, expected_fc3, 2e-7):
            reasons.append("fc3")
        if not close(predicted, expected_predicted, 2e-8):
            reasons.append("predicted_forces")

        for key in ("rank", "n_parameters", "symmetry_operation_count"):
            if int(observed[key]) != int(expected[key]):
                reasons.append(key)
        expected_singular = array(expected["singular_values"])
        singular = array(observed["singular_values"], expected_singular.shape)
        if not close(singular, expected_singular, 2e-8):
            reasons.append("singular_values")
        for key in ("condition_number", "residual_norm"):
            left = float(observed[key])
            right = float(expected[key])
            if not math.isfinite(left) or not math.isclose(
                    left, right, rel_tol=2e-8, abs_tol=2e-8):
                reasons.append(key)

        # Derivative-index permutation symmetry.
        if not close(fc2, fc2.transpose(1, 0, 3, 2), 2e-8, 0):
            reasons.append("fc2_permutation_invariant")
        if not close(fc3, fc3.transpose(1, 0, 2, 4, 3, 5), 2e-8, 0):
            reasons.append("fc3_first_second_permutation_invariant")
        if not close(fc3, fc3.transpose(0, 2, 1, 3, 5, 4), 2e-8, 0):
            reasons.append("fc3_second_third_permutation_invariant")

        # Acoustic sum rules on every atomic index.
        asr = max(
            float(np.max(np.abs(fc2.sum(axis=0)))),
            float(np.max(np.abs(fc2.sum(axis=1)))),
            float(np.max(np.abs(fc3.sum(axis=0)))),
            float(np.max(np.abs(fc3.sum(axis=1)))),
            float(np.max(np.abs(fc3.sum(axis=2)))),
        )
        metrics["acoustic_sum_rule_max_abs"] = asr
        if asr > 3e-8:
            reasons.append("acoustic_sum_rule_invariant")

        displacements = np.asarray(item["displacements"], dtype=float)
        internal_prediction = predict_forces(displacements, fc2, fc3)
        prediction_error = float(np.max(np.abs(internal_prediction - predicted)))
        metrics["prediction_consistency_max_abs"] = prediction_error
        if prediction_error > 2e-8:
            reasons.append("prediction_consistency_invariant")
        residual = float(np.linalg.norm(
            predicted - np.asarray(item["forces"], dtype=float)
        ))
        if not math.isclose(
                residual, float(observed["residual_norm"]),
                rel_tol=2e-9, abs_tol=2e-9):
            reasons.append("residual_consistency_invariant")
        net_force = float(np.max(np.abs(predicted.sum(axis=1))))
        metrics["predicted_net_force_max_abs"] = net_force
        if net_force > 3e-8:
            reasons.append("zero_net_force_invariant")

        symmetry_error = symmetry_force_error(item, fc2, fc3, predicted)
        metrics["symmetry_equivariance_max_abs"] = symmetry_error
        if symmetry_error > 2e-7:
            reasons.append("space_group_equivariance_invariant")

        rank = int(observed["rank"])
        if rank <= 0 or rank > int(observed["n_parameters"]):
            reasons.append("rank_invariant")
        if np.any(np.diff(singular) > 1e-10) or np.any(singular < 0):
            reasons.append("singular_value_order_invariant")
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        reasons.append(f"protocol:{type(exc).__name__}")
    return not reasons, sorted(set(reasons)), metrics


def cross_case_invariants(observed_by_name):
    failures = []
    try:
        base = observed_by_name["p1_transform_base"]["result"]
        rotated = observed_by_name["p1_transform_rotated"]["result"]
        angle = 0.53
        rotation = np.array([
            [math.cos(angle), -math.sin(angle), 0.0],
            [math.sin(angle), math.cos(angle), 0.0],
            [0.0, 0.0, 1.0],
        ])
        base_fc2 = array(base["fc2"])
        base_fc3 = array(base["fc3"])
        expected_fc2 = np.einsum(
            "aA,bB,ijAB->ijab", rotation, rotation, base_fc2, optimize=True
        )
        expected_fc3 = np.einsum(
            "aA,bB,cC,ijkABC->ijkabc",
            rotation, rotation, rotation, base_fc3, optimize=True,
        )
        if not close(array(rotated["fc2"]), expected_fc2, 3e-7):
            failures.append("rigid_rotation:fc2")
        if not close(array(rotated["fc3"]), expected_fc3, 3e-7):
            failures.append("rigid_rotation:fc3")

        original = observed_by_name["p1_permutation_base"]["result"]
        swapped = observed_by_name["p1_permutation_swapped"]["result"]
        order = np.array([2, 0, 1])
        original_fc2 = array(original["fc2"])
        original_fc3 = array(original["fc3"])
        expected_fc2 = original_fc2[order][:, order]
        expected_fc3 = original_fc3[order][:, order][:, :, order]
        if not close(array(swapped["fc2"]), expected_fc2, 3e-7):
            failures.append("atom_reordering:fc2")
        if not close(array(swapped["fc3"]), expected_fc3, 3e-7):
            failures.append("atom_reordering:fc3")
    except (KeyError, TypeError, ValueError) as exc:
        failures.append(f"cross_case_protocol:{type(exc).__name__}")
    return failures


def main():
    cases = hidden_cases()
    invalid = invalid_cases(cases[0])
    report = {
        "task": "ALGOBRIDGE-0019",
        "reference": (
            "locked phonopy 4bac506 to phono3py 2dc8200 "
            "produce_fc3(symfc 1.7.3)"
        ),
        "total": len(cases),
        "hard_gates": {},
    }
    try:
        reference = run_json(
            [sys.executable, "/opt/reference-runner/reference_runner.py"],
            {"cases": cases},
            env={
                **os.environ,
                "PYTHONPATH": "/opt/reference-runtime:/tests",
                "PYTHONNOUSERSITE": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
            },
        )
    except Exception as exc:
        fail(f"reference runner failed: {exc}", report)
    reference_errors = [
        item for item in reference["cases"] if "result" not in item
    ]
    if reference_errors:
        fail(f"locked reference omitted results: {reference_errors[:2]}", report)
    report["hard_gates"]["locked_reference"] = "pass"

    policy_ok, policy_detail = source_policy()
    if not policy_ok:
        fail(f"source policy failed: {policy_detail}", report)
    report["hard_gates"]["source_policy"] = policy_detail

    subprocess.run(["chown", "-R", "root:root", str(TESTBED)], check=True)
    subprocess.run(["chmod", "-R", "a+rX", str(TESTBED)], check=True)
    subprocess.run(["chmod", "-R", "a-w", str(TESTBED)], check=True)
    isolation_targets = (
        "/opt/reference-runtime", "/opt/reference-phono3py-source",
        "/opt/reference-runner", "/opt/source-archives", "/opt/wheels",
        "/opt/pristine-host",
    )
    for path in isolation_targets:
        shutil.rmtree(path, ignore_errors=True)
    if any(Path(path).exists() for path in isolation_targets):
        fail("reference isolation cleanup failed", report)
    report["hard_gates"]["reference_removed_before_candidate"] = "pass"

    home = Path("/tmp/candidate-home")
    home.mkdir(mode=0o700, exist_ok=True)
    shutil.chown(home, user=10001, group=10001)
    command = [
        "runuser", "-u", "candidate", "--", "env", "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp/candidate-home",
        "PYTHONNOUSERSITE=1", "PYTHONPATH=/testbed",
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
    for item in invalid:
        observed = observed_by_name.get(item["name"], {})
        if observed.get("error") not in {"TypeError", "ValueError"}:
            invalid_failures.append(item["name"])
    if invalid_failures:
        fail(f"invalid-input contract failed: {invalid_failures}", report)
    report["hard_gates"]["invalid_input_rejection"] = "pass"

    cross_failures = cross_case_invariants(observed_by_name)
    if cross_failures:
        fail(f"cross-case invariants failed: {cross_failures}", report)
    report["hard_gates"]["rotation_and_reordering_invariance"] = "pass"

    expected_by_name = {item["name"]: item for item in reference["cases"]}
    results = []
    passed = 0
    for item in cases:
        name = item["name"]
        expected_item = expected_by_name.get(name, {})
        observed_item = observed_by_name.get(name, {})
        if "result" not in expected_item:
            fail(f"reference omitted result for {name}", report)
        if "result" not in observed_item:
            ok, reasons, metrics = (
                False,
                [f"candidate_error:{observed_item.get('error', 'missing')}"] ,
                {},
            )
        else:
            ok, reasons, metrics = compare_case(
                item, expected_item["result"], observed_item["result"]
            )
        passed += int(ok)
        results.append({
            "name": name,
            "passed": ok,
            "reasons": reasons,
            "metrics": metrics,
        })

    reward = passed / len(cases)
    report.update({
        "status": "completed",
        "passed": passed,
        "failed": len(cases) - passed,
        "cases": results,
    })
    write_report(report, reward)


if __name__ == "__main__":
    main()
