#!/usr/bin/env python3
"""Separate clean-room differential verifier for ALGOBRIDGE-0027."""

from __future__ import annotations

import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import time
from collections import Counter

import numpy as np

from cases import hidden_cases


TESTBED = pathlib.Path("/testbed")
LOG_ROOT = pathlib.Path("/logs/verifier")
REFERENCE_PYTHON = "/opt/reference-venv/bin/python"
REFERENCE_RUNNER = "/opt/reference-runner/reference_runner.py"
CANDIDATE_RUNNER = "/opt/candidate-runner/candidate_runner.py"
SOURCE_LOCK = pathlib.Path("/opt/reference-runner/source-lock.json")
PRISTINE_HOST = pathlib.Path("/opt/pristine-host")
REFERENCE_HOST = pathlib.Path("/opt/reference-host")
REFERENCE_DONOR = pathlib.Path("/opt/reference-donor")
REFERENCE_VENV = pathlib.Path("/opt/reference-venv")
WHEEL_ROOT = pathlib.Path("/opt/wheels")
CANDIDATE_TOOLS = pathlib.Path("/opt/candidate-tools")
CANDIDATE_RUNTIME = pathlib.Path("/opt/candidate-runtime")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001

POINT_NAMES = [
    "binary_auto",
    "multiclass_auto",
    "binary_dict",
    "multiclass_dict",
    "string_labels",
    "duplicate_points",
    "equidistant_ties",
    "float32",
    "sample_weight_lineage",
    "binary_float_ratio",
    "all_classes",
    "high_dimensional",
    "segment_and_weight_invariants",
    "counts_prefix_determinism_and_ties",
    "api_contract_and_host_regression",
]


def log(message):
    print(message, flush=True)


def run_json(command, payload, *, env=None, as_candidate=False, timeout=240):
    def demote():
        os.setgroups([])
        os.setgid(CANDIDATE_GID)
        os.setuid(CANDIDATE_UID)

    completed = subprocess.run(
        command,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=demote if as_candidate and os.getuid() == 0 else None,
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
            f"runner returned non-JSON output: {completed.stdout[-4000:]}\n"
            f"stderr={completed.stderr[-4000:]}"
        ) from error


def source_scan():
    forbidden = re.compile(
        r"(^|[^A-Za-z0-9_])(imblearn|imbalanced[-_]learn|/opt/reference|/tests)([^A-Za-z0-9_]|$)",
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
        changed.append(str(relative))
        if path.stat().st_size > 500_000:
            findings.append(f"oversized changed file: {relative}")
            continue
        if path.suffix == ".so" or b"\x00" in candidate_bytes:
            findings.append(f"changed binary file is not permitted: {relative}")
            continue
        text = candidate_bytes.decode("utf-8", errors="replace")
        match = forbidden.search(text)
        if match:
            findings.append(
                f"forbidden donor/verifier reference in {relative}: {match.group(0)!r}"
            )
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
        timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(f"candidate materialization failed: {completed.stderr[-2000:]}")
    manifest = (CANDIDATE_RUNTIME / "OVERLAY-MANIFEST.txt").read_text().splitlines()
    return manifest, completed.stdout.strip()


def remove_reference_materials():
    for path in (
        REFERENCE_VENV,
        REFERENCE_DONOR,
        REFERENCE_HOST,
        PRISTINE_HOST,
        WHEEL_ROOT,
        CANDIDATE_TOOLS,
    ):
        if path.exists():
            shutil.rmtree(path)
    for path in (
        REFERENCE_PYTHON,
        "/opt/reference-donor/imblearn",
        "/opt/wheels",
        "/opt/pristine-host",
    ):
        if pathlib.Path(path).exists():
            raise RuntimeError(f"reference removal failed: {path}")


def lock_runtime_and_testbed():
    for path in (TESTBED, CANDIDATE_RUNTIME):
        ownership = subprocess.run(
            ["chown", "-R", "root:root", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        permissions = subprocess.run(
            ["chmod", "-R", "a-w", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        if ownership.returncode or permissions.returncode:
            raise RuntimeError(f"failed to lock {path}")


def probe_candidate_isolation(env):
    code = """
import json
import os
import pathlib
checks = {
    "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
    "reference_runner_unreadable": not os.access("/opt/reference-runner/reference_runner.py", os.R_OK),
    "reference_host_removed": not pathlib.Path("/opt/reference-host").exists(),
    "reference_donor_removed": not pathlib.Path("/opt/reference-donor").exists(),
    "reference_venv_removed": not pathlib.Path("/opt/reference-venv").exists(),
    "pristine_host_removed": not pathlib.Path("/opt/pristine-host").exists(),
    "wheelhouse_removed": not pathlib.Path("/opt/wheels").exists(),
    "candidate_tools_removed": not pathlib.Path("/opt/candidate-tools").exists(),
}
print(json.dumps(checks, sort_keys=True))
"""

    def demote():
        os.setgroups([])
        os.setgid(CANDIDATE_GID)
        os.setuid(CANDIDATE_UID)

    completed = subprocess.run(
        [sys.executable, "-I", "-c", code],
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=demote if os.getuid() == 0 else None,
        timeout=30,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"candidate isolation probe failed: {completed.stderr[-1000:]}")
    return json.loads(completed.stdout)


def max_abs_error(left, right):
    left = np.asarray(left, dtype=float)
    right = np.asarray(right, dtype=float)
    if left.shape != right.shape:
        return math.inf
    if left.size == 0:
        return 0.0
    return float(np.max(np.abs(left - right)))


def compare_case(reference, candidate):
    details = {}
    exact_fields = ["name", "y", "X_dtype", "y_dtype", "sampling_strategy", "parent_indices"]
    exact = {field: reference[field] == candidate[field] for field in exact_fields}
    details["exact_fields"] = exact
    X_error = max_abs_error(reference["X"], candidate["X"])
    lambda_error = max_abs_error(reference["lambdas"], candidate["lambdas"])
    if reference["sample_weight"] is None or candidate["sample_weight"] is None:
        weight_match = reference["sample_weight"] is candidate["sample_weight"]
        weight_error = 0.0 if weight_match else math.inf
    else:
        weight_error = max_abs_error(
            reference["sample_weight"], candidate["sample_weight"]
        )
    details.update(
        X_max_abs_error=X_error,
        lambda_max_abs_error=lambda_error,
        weight_max_abs_error=weight_error,
    )
    passed = (
        all(exact.values())
        and X_error <= 1e-12
        and lambda_error <= 1e-15
        and weight_error <= 1e-12
    )
    return passed, details


def segment_and_weight_invariants(cases, candidates, references):
    failures = []
    for spec, wrapper, reference in zip(cases, candidates, references, strict=True):
        if not wrapper.get("ok"):
            failures.append(f"{spec['name']}: candidate error")
            continue
        result = wrapper["result"]
        X_input = np.asarray(spec["X"], dtype=spec["dtype"])
        y_input = np.asarray(spec["y"])
        X_result = np.asarray(result["X"], dtype=spec["dtype"])
        y_result = np.asarray(result["y"])
        original_count = len(X_input)
        if len(X_result) != len(reference["X"]):
            failures.append(f"{spec['name']}: incorrect synthetic row count")
        if not np.array_equal(X_result[:original_count], X_input):
            failures.append(f"{spec['name']}: original X prefix changed")
        if not np.array_equal(y_result[:original_count], y_input):
            failures.append(f"{spec['name']}: original y prefix changed")
        parents = np.asarray(result["parent_indices"], dtype=int).reshape(-1, 2)
        lambdas = np.asarray(result["lambdas"], dtype=float)
        for offset, ((parent, neighbor), step) in enumerate(
            zip(parents, lambdas, strict=True)
        ):
            if not (0 <= parent < original_count and 0 <= neighbor < original_count):
                failures.append(f"{spec['name']}: invalid provenance index")
                continue
            if y_input[parent] != y_input[neighbor]:
                failures.append(f"{spec['name']}: cross-class interpolation")
            if not 0.0 <= step < 1.0:
                failures.append(f"{spec['name']}: lambda outside [0, 1)")
            expected = X_input[parent] + step * (X_input[neighbor] - X_input[parent])
            tolerance = 2e-6 if spec["dtype"] == "float32" else 1e-12
            if not np.allclose(
                X_result[original_count + offset], expected, rtol=0.0, atol=tolerance
            ):
                failures.append(f"{spec['name']}: synthetic row is off segment")
            if y_result[original_count + offset] != y_input[parent]:
                failures.append(f"{spec['name']}: synthetic label is incorrect")
        if spec.get("sample_weight") is not None and result["sample_weight"] is not None:
            input_weight = np.asarray(spec["sample_weight"], dtype=float)
            output_weight = np.asarray(result["sample_weight"], dtype=float)
            if not np.array_equal(output_weight[:original_count], input_weight):
                failures.append(f"{spec['name']}: original sample weights changed")
            for offset, ((parent, neighbor), step) in enumerate(
                zip(parents, lambdas, strict=True)
            ):
                expected = (1 - step) * input_weight[parent] + step * input_weight[neighbor]
                if not math.isclose(
                    output_weight[original_count + offset], expected, rel_tol=0.0, abs_tol=1e-12
                ):
                    failures.append(f"{spec['name']}: weight lineage mismatch")
    return not failures, {"failures": failures[:30]}


def count_prefix_determinism(cases, candidates, rerun, references):
    failures = []
    for spec, first, second, reference in zip(
        cases, candidates, rerun, references, strict=True
    ):
        if not first.get("ok") or not second.get("ok"):
            failures.append(f"{spec['name']}: candidate error")
            continue
        if first["result"] != second["result"]:
            failures.append(f"{spec['name']}: fixed seed is not deterministic")
        result = first["result"]
        actual_counts = Counter(result["y"])
        expected_counts = Counter(reference["y"])
        if actual_counts != expected_counts:
            for label, expected in expected_counts.items():
                if actual_counts[label] == expected:
                    continue
                failures.append(f"{spec['name']}: target count mismatch for {label!r}")
    return not failures, {"failures": failures[:30]}


def run_host_regression(env):
    def demote():
        os.setgroups([])
        os.setgid(CANDIDATE_GID)
        os.setuid(CANDIDATE_UID)

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
            "-p",
            "sklearn.conftest",
            str(CANDIDATE_RUNTIME / "sklearn/preprocessing/tests"),
        ],
        cwd="/tmp",
        env=regression_env,
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
        preexec_fn=demote if os.getuid() == 0 else None,
    )
    return completed.returncode == 0, {
        "returncode": completed.returncode,
        "stdout_head": completed.stdout[:5000],
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }


def main():
    started = time.time()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    report = {
        "task": "algobridge-0027__scikit-learn__absorbs__imbalanced-learn",
        "points": [],
        "hard_gates": {},
    }
    reward = 0.0
    try:
        locks = json.loads(SOURCE_LOCK.read_text())
        cases = hidden_cases()
        payload = {"cases": cases}
        reference_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": str(REFERENCE_DONOR),
            "PYTHONNOUSERSITE": "1",
            "HOME": "/tmp/reference-home",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        }
        reference, reference_stderr = run_json(
            [REFERENCE_PYTHON, REFERENCE_RUNNER],
            payload,
            env=reference_env,
            timeout=300,
        )
        provenance = reference["provenance"]
        reference_ok = (
            provenance["sklearn_version"] == "1.10.dev0"
            and provenance["sklearn_file"].startswith("/opt/reference-venv/")
            and provenance["imblearn_version"] == "0.15.dev0"
            and provenance["imblearn_file"].startswith("/opt/reference-donor/")
            and locks["host"]["head_commit"]
            == "e27ccf58592fcfe8c7ca87f53dde840c436093b2"
            and locks["donor"]["head_commit"]
            == "8504e95f0160f61d1b617ca66f779646d2ee609e"
        )
        report["reference"] = {
            "provenance": provenance,
            "locked_host_commit": locks["host"]["head_commit"],
            "locked_donor_commit": locks["donor"]["head_commit"],
            "stderr_tail": reference_stderr[-1000:],
        }
        report["hard_gates"]["locked_reference_pipeline"] = reference_ok
        if not reference_ok:
            raise RuntimeError("locked reference provenance check failed")

        findings, changed = source_scan()
        report["source_scan"] = {"changed_files": changed, "findings": findings}
        report["hard_gates"]["forbidden_dependency_scan"] = not findings
        if findings:
            raise RuntimeError("candidate contains forbidden donor/verifier dependency")

        overlay_manifest, materializer_output = materialize_candidate()
        report["candidate_overlay"] = {
            "manifest": overlay_manifest,
            "materializer_output": materializer_output,
        }
        report["hard_gates"]["trusted_host_overlay"] = all(
            path.startswith("sklearn/") and path.endswith(".py")
            for path in overlay_manifest
        )
        if not report["hard_gates"]["trusted_host_overlay"]:
            raise RuntimeError("candidate overlay contains an invalid path")

        remove_reference_materials()
        report["hard_gates"]["reference_removed_before_candidate"] = True
        lock_runtime_and_testbed()
        report["hard_gates"]["candidate_trees_locked"] = True

        candidate_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONNOUSERSITE": "1",
            "HOME": "/tmp/candidate-home",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        }
        pathlib.Path(candidate_env["HOME"]).mkdir(exist_ok=True)
        os.chown(candidate_env["HOME"], CANDIDATE_UID, CANDIDATE_GID)
        isolation = probe_candidate_isolation(candidate_env)
        report["candidate_isolation_probe"] = isolation
        report["hard_gates"]["candidate_private_paths_inaccessible"] = all(
            isolation.values()
        )
        if not all(isolation.values()):
            raise RuntimeError(f"candidate isolation failed: {isolation}")

        candidate, candidate_stderr = run_json(
            [sys.executable, "-I", CANDIDATE_RUNNER],
            payload,
            env=candidate_env,
            as_candidate=True,
            timeout=300,
        )
        candidate_runtime_ok = (
            candidate.get("fatal") is None
            and str(candidate.get("sklearn_file", "")).startswith(
                "/opt/candidate-runtime/"
            )
            and str(candidate.get("smote_module", "")).startswith(
                "/opt/candidate-runtime/"
            )
            and candidate.get("isolation_checks")
            and all(candidate["isolation_checks"].values())
        )
        report["candidate"] = {
            "fatal": candidate.get("fatal"),
            "sklearn_file": candidate.get("sklearn_file"),
            "sklearn_version": candidate.get("sklearn_version"),
            "smote_module": candidate.get("smote_module"),
            "isolation_checks": candidate.get("isolation_checks"),
            "stderr_tail": candidate_stderr[-1000:],
        }
        report["hard_gates"]["candidate_clean_runtime"] = candidate_runtime_ok
        if not candidate_runtime_ok:
            raise RuntimeError(f"candidate runner failed: {candidate.get('fatal')}")

        references = reference["results"]
        candidates = candidate["results"]
        if len(references) != 12 or len(candidates) != 12:
            raise RuntimeError("runner returned incorrect case count")
        for name, expected, actual in zip(
            POINT_NAMES[:12], references, candidates, strict=True
        ):
            if actual.get("ok"):
                passed, details = compare_case(expected, actual["result"])
            else:
                passed, details = False, {"candidate_error": actual.get("error")}
            report["points"].append({"name": name, "passed": passed, **details})

        invariant_passed, invariant_details = segment_and_weight_invariants(
            cases, candidates, references
        )
        report["points"].append(
            {
                "name": POINT_NAMES[12],
                "passed": invariant_passed,
                **invariant_details,
            }
        )

        rerun, _ = run_json(
            [sys.executable, "-I", CANDIDATE_RUNNER],
            payload,
            env=candidate_env,
            as_candidate=True,
            timeout=300,
        )
        deterministic_passed, deterministic_details = count_prefix_determinism(
            cases, candidates, rerun["results"], references
        )
        report["points"].append(
            {
                "name": POINT_NAMES[13],
                "passed": deterministic_passed,
                **deterministic_details,
            }
        )

        contract_ok = all(
            item.get("rejected") for item in candidate.get("contract_checks", [])
        ) and len(candidate.get("contract_checks", [])) == 8
        host_ok, host_details = run_host_regression(candidate_env)
        report["host_regression"] = host_details
        report["hard_gates"]["host_regression"] = host_ok
        report["points"].append(
            {
                "name": POINT_NAMES[14],
                "passed": contract_ok and host_ok,
                "contract_checks": candidate.get("contract_checks", []),
                "host_regression_passed": host_ok,
            }
        )

        hard_gates_passed = all(report["hard_gates"].values())
        passed_count = sum(point["passed"] for point in report["points"])
        reward = passed_count / len(POINT_NAMES) if hard_gates_passed else 0.0
        report.update(
            passed=passed_count,
            total=len(POINT_NAMES),
            hard_gates_passed=hard_gates_passed,
            reward=reward,
        )
    except Exception as error:
        report.update(
            passed=0,
            total=len(POINT_NAMES),
            hard_gates_passed=False,
            reward=0.0,
            fatal_error=f"{type(error).__name__}: {error}",
        )
        log(f"FATAL: {type(error).__name__}: {error}")
    finally:
        report["elapsed_seconds"] = time.time() - started
        (LOG_ROOT / "report.json").write_text(
            json.dumps(report, indent=2, sort_keys=True)
        )
        (LOG_ROOT / "reward.txt").write_text(f"{reward:.12g}\n")
        log(
            f"RESULT: {report.get('passed', 0)}/{report.get('total', len(POINT_NAMES))} "
            f"Reward={reward:.12g} hard_gates={report.get('hard_gates_passed', False)}"
        )
        for point in report.get("points", []):
            log(f"  {'PASS' if point['passed'] else 'FAIL'} {point['name']}")


if __name__ == "__main__":
    main()
