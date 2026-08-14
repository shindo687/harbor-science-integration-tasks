#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0012."""

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
import site
import subprocess
import sys
import tokenize

import numpy as np

from cases import hidden_cases, permutation_pair, transformed_pair
from model import adjacency, component_count, statistics


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-prody-source")
ANALYSIS = Path("python_packaging/gmxapi/src/gmxapi/analysis")
MODULE = ANALYSIS / "anm.py"
INIT = ANALYSIS / "__init__.py"
FORBIDDEN = re.compile(
    r"\b(prody|scipy|biopython|subprocess|ctypes|cffi|socket|requests|urllib|"
    r"importlib|runpy|pickle|marshal)\b|__import__|os\s*\.\s*system|"
    r"\bpopen\s*\(|\bexec\s*\(|\beval\s*\(",
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
        DONOR / "prody/dynamics/anm.py",
        DONOR / "prody/dynamics/analysis.py",
        DONOR / "prody/dynamics/nma.py",
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
    expected_added = {str(MODULE), str(INIT)}
    if missing:
        return False, f"host files removed: {missing[:4]}"
    if changed:
        return False, f"locked host files changed: {changed[:4]}"
    if set(added) != expected_added:
        return False, f"unexpected added files: {added[:4]}"
    for relative in (MODULE, INIT):
        path = TESTBED / relative
        if not path.is_file():
            return False, f"missing {relative}"
        if path.stat().st_size > 100_000:
            return False, f"candidate file exceeds 100000 bytes: {relative}"
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return False, f"candidate file is not UTF-8: {relative}"
        if FORBIDDEN.search(text):
            return False, "candidate contains a forbidden dependency or execution primitive"
    init_tokens = normalized_tokens(TESTBED / INIT)
    if "analyze_anm" not in init_tokens or "anm" not in init_tokens:
        return False, "analysis package does not export analyze_anm"
    tokens = normalized_tokens(TESTBED / MODULE)
    fragments = donor_fragments()
    for size in (96, 64):
        if any(tuple(tokens[index:index + size]) in fragments
               for index in range(max(0, len(tokens) - size + 1))):
            return False, f"candidate contains a normalized donor fragment ({size} tokens)"
    return True, {
        "added": added,
        "module_sha256": sha256(TESTBED / MODULE),
        "module_bytes": (TESTBED / MODULE).stat().st_size,
        "donor_fragment_scan": "pass",
    }


def invalid_cases(valid):
    cases = []

    bad_shape = copy.deepcopy(valid)
    bad_shape["name"] = "invalid_bad_shape"
    bad_shape["coordinates_nm"] = np.asarray(
        bad_shape["coordinates_nm"]
    )[:, :2].tolist()
    cases.append(bad_shape)

    nonfinite = copy.deepcopy(valid)
    nonfinite["name"] = "invalid_nonfinite"
    nonfinite["coordinates_nm"][0][0] = float("nan")
    cases.append(nonfinite)

    duplicate_selection = copy.deepcopy(valid)
    duplicate_selection["name"] = "invalid_duplicate_selection"
    duplicate_selection["arguments"]["selection"] = [0, 1, 1, 2]
    cases.append(duplicate_selection)

    bad_index = copy.deepcopy(valid)
    bad_index["name"] = "invalid_selection_index"
    bad_index["arguments"]["selection"] = [0, 1, 2, 999]
    cases.append(bad_index)

    low_cutoff = copy.deepcopy(valid)
    low_cutoff["name"] = "invalid_low_cutoff"
    low_cutoff["arguments"]["cutoff_nm"] = 0.39
    cases.append(low_cutoff)

    zero_gamma = copy.deepcopy(valid)
    zero_gamma["name"] = "invalid_zero_gamma"
    zero_gamma["arguments"]["gamma"] = 0.0
    cases.append(zero_gamma)

    bool_modes = copy.deepcopy(valid)
    bool_modes["name"] = "invalid_boolean_modes"
    bool_modes["arguments"]["n_modes"] = True
    cases.append(bool_modes)

    duplicate_coordinates = copy.deepcopy(valid)
    duplicate_coordinates["name"] = "invalid_duplicate_coordinates"
    duplicate_coordinates["coordinates_nm"][1] = list(
        duplicate_coordinates["coordinates_nm"][0]
    )
    cases.append(duplicate_coordinates)
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


def compare_case(case, expected, observed):
    reasons = []
    metrics = {}
    try:
        selection = case["arguments"].get("selection")
        node_count = (
            len(case["coordinates_nm"]) if selection is None else len(selection)
        )
        mode_count = len(expected["eigenvalues"])
        hessian_shape = (3 * node_count, 3 * node_count)
        mode_shape = (3 * node_count, mode_count)
        matrix_shape = (node_count, node_count)
        expected_hessian = array(expected["hessian"], hessian_shape)
        hessian = array(observed["hessian"], hessian_shape)
        expected_eigenvalues = array(expected["eigenvalues"], (mode_count,))
        eigenvalues = array(observed["eigenvalues"], (mode_count,))
        expected_modes = array(expected["modes"], mode_shape)
        modes = array(observed["modes"], mode_shape)
        expected_covariance = array(expected["covariance"], hessian_shape)
        covariance = array(observed["covariance"], hessian_shape)
        expected_msf = array(expected["msf"], (node_count,))
        msf = array(observed["msf"], (node_count,))
        expected_correlation = array(
            expected["cross_correlation"], matrix_shape
        )
        correlation = array(observed["cross_correlation"], matrix_shape)

        expected_indices = np.asarray(expected["node_indices"], dtype=int)
        indices = np.asarray(observed["node_indices"])
        if indices.shape != expected_indices.shape or not np.array_equal(
                indices, expected_indices):
            reasons.append("node_indices")
        for key in ("zero_mode_count", "component_count"):
            if int(observed[key]) != int(expected[key]):
                reasons.append(key)

        metrics["hessian_max_abs"] = float(
            np.max(np.abs(hessian - expected_hessian))
        )
        metrics["eigenvalue_max_abs"] = float(
            np.max(np.abs(eigenvalues - expected_eigenvalues))
        )
        projector = modes @ modes.T
        expected_projector = expected_modes @ expected_modes.T
        metrics["mode_projector_max_abs"] = float(
            np.max(np.abs(projector - expected_projector))
        )
        metrics["covariance_max_abs"] = float(
            np.max(np.abs(covariance - expected_covariance))
        )
        metrics["msf_max_abs"] = float(np.max(np.abs(msf - expected_msf)))
        metrics["correlation_max_abs"] = float(
            np.max(np.abs(correlation - expected_correlation))
        )
        if not close(hessian, expected_hessian, 2e-9):
            reasons.append("hessian")
        if not close(eigenvalues, expected_eigenvalues, 2e-8):
            reasons.append("eigenvalues")
        if not close(projector, expected_projector, 3e-7):
            reasons.append("mode_subspace")
        if not close(covariance, expected_covariance, 2e-7):
            reasons.append("covariance")
        if not close(msf, expected_msf, 2e-7):
            reasons.append("msf")
        if not close(correlation, expected_correlation, 8e-7):
            reasons.append("cross_correlation")

        symmetry_error = float(np.max(np.abs(hessian - hessian.T)))
        block_sum = hessian.reshape(
            node_count, 3, node_count, 3
        ).sum(axis=2)
        block_sum_error = float(np.max(np.abs(block_sum)))
        all_eigenvalues = np.linalg.eigvalsh(hessian)
        minimum_eigenvalue = float(all_eigenvalues[0])
        zero_count = int(np.sum(all_eigenvalues < 1e-6))
        metrics.update({
            "hessian_symmetry_max_abs": symmetry_error,
            "block_row_sum_max_abs": block_sum_error,
            "minimum_hessian_eigenvalue": minimum_eigenvalue,
        })
        if symmetry_error > 2e-10:
            reasons.append("hessian_symmetry_invariant")
        if block_sum_error > 2e-9:
            reasons.append("translation_sum_rule_invariant")
        if minimum_eigenvalue < -2e-8:
            reasons.append("positive_semidefinite_invariant")
        if zero_count != int(observed["zero_mode_count"]):
            reasons.append("zero_mode_diagnostic_invariant")
        if zero_count < 3 * int(observed["component_count"]):
            reasons.append("component_translation_modes_invariant")

        orthogonality_error = float(
            np.max(np.abs(modes.T @ modes - np.eye(mode_count)))
        )
        residual_error = float(np.max(np.abs(
            hessian @ modes - modes * eigenvalues[None, :]
        )))
        metrics["mode_orthogonality_max_abs"] = orthogonality_error
        metrics["eigen_residual_max_abs"] = residual_error
        if orthogonality_error > 3e-7:
            reasons.append("mode_orthogonality_invariant")
        if residual_error > 3e-7:
            reasons.append("eigen_residual_invariant")

        reconstructed = (modes * (1.0 / eigenvalues)[None, :]) @ modes.T
        reconstruction_error = float(np.max(np.abs(covariance - reconstructed)))
        covariance_symmetry = float(np.max(np.abs(covariance - covariance.T)))
        covariance_minimum = float(np.linalg.eigvalsh(covariance)[0])
        calculated_msf, calculated_correlation = statistics(
            covariance, node_count
        )
        statistics_error = max(
            float(np.max(np.abs(msf - calculated_msf))),
            float(np.max(np.abs(correlation - calculated_correlation))),
        )
        metrics.update({
            "covariance_reconstruction_max_abs": reconstruction_error,
            "covariance_symmetry_max_abs": covariance_symmetry,
            "minimum_covariance_eigenvalue": covariance_minimum,
            "statistics_consistency_max_abs": statistics_error,
        })
        if reconstruction_error > 3e-7:
            reasons.append("covariance_reconstruction_invariant")
        if covariance_symmetry > 3e-9 or covariance_minimum < -2e-7:
            reasons.append("covariance_psd_invariant")
        if statistics_error > 8e-7:
            reasons.append("mode_statistics_invariant")
        if not close(correlation, correlation.T, 2e-9, 0):
            reasons.append("correlation_symmetry_invariant")
        if not close(np.diag(correlation), np.ones(node_count), 2e-8, 0):
            reasons.append("correlation_diagonal_invariant")

        selected = np.asarray(case["coordinates_nm"], dtype=float)[expected_indices]
        graph = adjacency(selected, case["arguments"]["cutoff_nm"])
        if component_count(graph) != int(observed["component_count"]):
            reasons.append("component_count_invariant")
    except (KeyError, TypeError, ValueError, OverflowError, np.linalg.LinAlgError) as exc:
        reasons.append(f"protocol:{type(exc).__name__}")
    return not reasons, sorted(set(reasons)), metrics


def cross_case_invariants(observed):
    failures = []
    try:
        gamma_base = observed["gamma_scaling_base"]["result"]
        gamma_scaled = observed["gamma_scaling_tripled"]["result"]
        if not close(array(gamma_scaled["hessian"]),
                     3.0 * array(gamma_base["hessian"]), 3e-8):
            failures.append("gamma_scaling:hessian")
        if not close(array(gamma_scaled["eigenvalues"]),
                     3.0 * array(gamma_base["eigenvalues"]), 3e-7):
            failures.append("gamma_scaling:eigenvalues")
        if not close(array(gamma_scaled["covariance"]),
                     array(gamma_base["covariance"]) / 3.0, 3e-7):
            failures.append("gamma_scaling:covariance")
        if not close(array(gamma_scaled["msf"]),
                     array(gamma_base["msf"]) / 3.0, 3e-7):
            failures.append("gamma_scaling:msf")
        if not close(array(gamma_scaled["cross_correlation"]),
                     array(gamma_base["cross_correlation"]), 3e-7):
            failures.append("gamma_scaling:correlation")

        rigid_base = observed["rigid_transform_base"]["result"]
        rigid_moved = observed["rigid_transform_moved"]["result"]
        _, _, rotation = transformed_pair()
        node_count = len(rigid_base["node_indices"])
        base_hessian = array(rigid_base["hessian"]).reshape(
            node_count, 3, node_count, 3
        )
        expected_hessian = np.einsum(
            "aA,iAjB,bB->iajb",
            rotation,
            base_hessian,
            rotation,
            optimize=True,
        ).reshape(3 * node_count, 3 * node_count)
        if not close(array(rigid_moved["hessian"]), expected_hessian, 4e-8):
            failures.append("rigid_transform:hessian")
        if not close(array(rigid_moved["eigenvalues"]),
                     array(rigid_base["eigenvalues"]), 3e-7):
            failures.append("rigid_transform:eigenvalues")
        if not close(array(rigid_moved["msf"]),
                     array(rigid_base["msf"]), 3e-7):
            failures.append("rigid_transform:msf")
        if not close(array(rigid_moved["cross_correlation"]),
                     array(rigid_base["cross_correlation"]), 3e-7):
            failures.append("rigid_transform:correlation")

        permutation_base = observed["atom_permutation_base"]["result"]
        permutation_swapped = observed["atom_permutation_swapped"]["result"]
        _, _, order = permutation_pair()
        count = len(order)
        base_hessian = array(permutation_base["hessian"]).reshape(
            count, 3, count, 3
        )
        expected_hessian = base_hessian[order][:, :, order, :].reshape(
            3 * count, 3 * count
        )
        base_covariance = array(permutation_base["covariance"]).reshape(
            count, 3, count, 3
        )
        expected_covariance = base_covariance[order][:, :, order, :].reshape(
            3 * count, 3 * count
        )
        if not close(array(permutation_swapped["hessian"]),
                     expected_hessian, 4e-8):
            failures.append("atom_permutation:hessian")
        if not close(array(permutation_swapped["covariance"]),
                     expected_covariance, 4e-7):
            failures.append("atom_permutation:covariance")
        if not close(array(permutation_swapped["msf"]),
                     array(permutation_base["msf"])[order], 4e-7):
            failures.append("atom_permutation:msf")
        expected_correlation = array(
            permutation_base["cross_correlation"]
        )[order][:, order]
        if not close(array(permutation_swapped["cross_correlation"]),
                     expected_correlation, 4e-7):
            failures.append("atom_permutation:correlation")
    except (KeyError, TypeError, ValueError, np.linalg.LinAlgError) as exc:
        failures.append(f"cross_case_protocol:{type(exc).__name__}")
    return failures


def remove_agent_absent_dependencies():
    for root in map(Path, site.getsitepackages()):
        patterns = (
            "scipy", "scipy-*.dist-info", "Bio", "biopython-*.dist-info",
            "pyparsing", "pyparsing.py", "pyparsing-*.dist-info",
        )
        for pattern in patterns:
            for path in root.glob(pattern):
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)


def main():
    cases = hidden_cases()
    invalid = invalid_cases(cases[0])
    report = {
        "task": "ALGOBRIDGE-0012",
        "reference": (
            "locked GROMACS coordinate contract to ProDy 7969f497 "
            "ANM.buildHessian/calcModes"
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
                "PRODY_VERBOSITY": "none",
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
        "/opt/reference-runtime", "/opt/reference-prody-source",
        "/opt/reference-runner", "/opt/source-archives", "/opt/wheels",
        "/opt/pristine-host",
    )
    for path in isolation_targets:
        shutil.rmtree(path, ignore_errors=True)
    remove_agent_absent_dependencies()
    if any(Path(path).exists() for path in isolation_targets):
        fail("reference isolation cleanup failed", report)
    report["hard_gates"]["reference_removed_before_candidate"] = "pass"

    home = Path("/tmp/candidate-home")
    home.mkdir(mode=0o700, exist_ok=True)
    shutil.chown(home, user=10001, group=10001)
    command = [
        "runuser", "-u", "candidate", "--", "env", "-i",
        "PATH=/usr/local/bin:/usr/bin:/bin", "HOME=/tmp/candidate-home",
        "PYTHONNOUSERSITE=1", "OPENBLAS_NUM_THREADS=1", "OMP_NUM_THREADS=1",
        sys.executable, "/opt/candidate-runner/candidate_runner.py",
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
    report["hard_gates"]["transform_scaling_reordering_invariance"] = "pass"

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
                False,
                [f"candidate_error:{observed_item.get('error', 'missing')}"] ,
                {},
            )
        else:
            ok, reasons, metrics = compare_case(
                case, expected_item["result"], observed_item["result"]
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
