#!/usr/bin/env python3
"""Separate, clean-room differential verifier for ALGOBRIDGE-0029."""

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
from collections import defaultdict

import numpy as np

from cases import hidden_cases, insertion_order_variant

TESTBED = pathlib.Path("/testbed")
LOG_ROOT = pathlib.Path("/logs/verifier")
REFERENCE_PYTHON = "/opt/reference-venv/bin/python"
REFERENCE_RUNNER = "/opt/reference-runner/reference_runner.py"
CANDIDATE_RUNNER = "/opt/candidate-runner/candidate_runner.py"
SOURCE_LOCK = "/opt/reference-runner/source-lock.json"
DONOR_ROOT = pathlib.Path("/opt/reference-venv")
REFERENCE_HOST = pathlib.Path("/opt/reference-host")
WHEEL_ROOT = pathlib.Path("/opt/wheels")
PUBLIC_PATH = pathlib.Path("/examples")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001

POINT_NAMES = [
    "two_moons",
    "weighted_sbm",
    "disconnected_components",
    "isolates",
    "weighted_ties",
    "degenerate_eigenspace",
    "heterogeneous_degree",
    "weighted_path",
    "ring_of_cliques",
    "weighted_grid",
    "barbell",
    "four_blocks",
    "node_insertion_order_invariant",
    "disconnected_components_not_mixed",
    "api_contract_and_host_regression",
]


def log(message):
    print(message, flush=True)


def run(command, **kwargs):
    return subprocess.run(command, check=False, text=True, **kwargs)


def run_json(command, payload, env=None, as_candidate=False, timeout=180):
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
        cwd="/tmp" if as_candidate else None,
        preexec_fn=demote if as_candidate and os.getuid() == 0 else None,
        timeout=timeout,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {command}\n"
            f"stdout={completed.stdout[-2000:]}\nstderr={completed.stderr[-4000:]}"
        )
    try:
        return json.loads(completed.stdout), completed.stderr
    except json.JSONDecodeError as error:
        raise RuntimeError(
            f"non-JSON runner output: {completed.stdout[-4000:]}\n{completed.stderr[-4000:]}"
        ) from error


def source_scan():
    forbidden_text = re.compile(
        r"(^|[^A-Za-z0-9_])(sklearn|scikit[-_]learn|/opt/scikit-learn|/opt/reference|/tests)([^A-Za-z0-9_]|$)",
        re.IGNORECASE,
    )
    findings = []
    for path in sorted(TESTBED.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(TESTBED)
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts):
            continue
        pristine = REFERENCE_HOST / relative
        candidate_bytes = path.read_bytes()
        if pristine.is_file() and candidate_bytes == pristine.read_bytes():
            continue
        if path.stat().st_size > 500_000:
            findings.append(f"oversized changed file: {relative}")
            continue
        if path.suffix == ".so":
            findings.append(f"candidate binary extension not permitted: {relative}")
            continue
        if b"\x00" in candidate_bytes:
            findings.append(f"changed binary file not permitted: {relative}")
            continue
        text = candidate_bytes.decode("utf-8", errors="replace")
        match = forbidden_text.search(text)
        if match:
            findings.append(f"forbidden donor/verifier reference in {relative}: {match.group(0)!r}")
    return findings


def remove_donor():
    if DONOR_ROOT.exists():
        shutil.rmtree(DONOR_ROOT)
    if REFERENCE_HOST.exists():
        shutil.rmtree(REFERENCE_HOST)
    if WHEEL_ROOT.exists():
        shutil.rmtree(WHEEL_ROOT)
    for path in (REFERENCE_PYTHON, "/usr/local/bin/sklearn", "/opt/wheels"):
        if pathlib.Path(path).exists():
            raise RuntimeError(f"donor removal failed: {path}")


def lock_candidate_tree():
    """Make the transferred artifact root-owned and immutable to the runner."""
    ownership = subprocess.run(
        ["chown", "-R", "root:root", str(TESTBED)],
        capture_output=True,
        text=True,
        check=False,
    )
    permissions = subprocess.run(
        ["chmod", "-R", "a-w", str(TESTBED)],
        capture_output=True,
        text=True,
        check=False,
    )
    if ownership.returncode or permissions.returncode:
        raise RuntimeError(
            "failed to lock candidate tree: "
            f"chown={ownership.stderr[-500:]} chmod={permissions.stderr[-500:]}"
        )


def probe_candidate_isolation(env):
    """Check private paths in a clean UID-10001 process before candidate import."""
    code = """
import json
import os
import pathlib

checks = {
    "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
    "reference_runner_unreadable": not os.access(
        "/opt/reference-runner/reference_runner.py", os.R_OK
    ),
    "reference_host_removed": not pathlib.Path("/opt/reference-host").exists(),
    "reference_venv_removed": not pathlib.Path("/opt/reference-venv").exists(),
    "wheelhouse_removed": not pathlib.Path("/opt/wheels").exists(),
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


def canonical_partition(labels):
    groups = defaultdict(list)
    for index, label in enumerate(labels):
        groups[int(label)].append(index)
    return sorted((tuple(group) for group in groups.values()))


def adjusted_rand_index(left, right):
    if len(left) != len(right):
        return -1.0
    count = len(left)
    table = defaultdict(int)
    rows = defaultdict(int)
    cols = defaultdict(int)
    for a, b in zip(left, right, strict=True):
        table[(a, b)] += 1
        rows[a] += 1
        cols[b] += 1

    choose2 = lambda value: value * (value - 1) / 2
    index = sum(choose2(value) for value in table.values())
    row_pairs = sum(choose2(value) for value in rows.values())
    col_pairs = sum(choose2(value) for value in cols.values())
    total_pairs = choose2(count)
    expected = row_pairs * col_pairs / total_pairs if total_pairs else 0.0
    maximum = 0.5 * (row_pairs + col_pairs)
    denominator = maximum - expected
    if denominator == 0:
        return 1.0 if canonical_partition(left) == canonical_partition(right) else 0.0
    return (index - expected) / denominator


def orthonormal_projector(embedding):
    array = np.asarray(embedding, dtype=float)
    q, _ = np.linalg.qr(array)
    return q @ q.T


def compare_case(reference, candidate):
    details = {}
    if reference["nodes"] != candidate["nodes"]:
        return False, {"node_order": "mismatch"}
    ari = adjusted_rand_index(reference["labels"], candidate["labels"])
    details["ari"] = ari
    try:
        projector_error = float(
            np.linalg.norm(
                orthonormal_projector(reference["embedding"])
                - orthonormal_projector(candidate["embedding"]),
                ord=2,
            )
        )
    except Exception as error:
        return False, {"ari": ari, "projector_error": f"{type(error).__name__}: {error}"}
    eigenvalue_error = float(
        np.max(
            np.abs(
                np.asarray(reference["eigenvalues"], dtype=float)
                - np.asarray(candidate["eigenvalues"], dtype=float)
            )
        )
    )
    ncut_error = abs(float(reference["normalized_cut"]) - float(candidate["normalized_cut"]))
    details.update(
        projector_error=projector_error,
        eigenvalue_error=eigenvalue_error,
        normalized_cut_error=ncut_error,
    )
    passed = (
        math.isclose(ari, 1.0, rel_tol=0.0, abs_tol=1e-12)
        and projector_error <= 1e-6
        and eigenvalue_error <= 1e-8
        and ncut_error <= 1e-8
    )
    return passed, details


def component_invariant(case, candidate):
    adjacency = defaultdict(set)
    for u, v, weight in case["edges"]:
        if weight != 0:
            adjacency[u].add(v)
            adjacency[v].add(u)
    components = []
    unseen = set(case["nodes"])
    while unseen:
        start = min(unseen, key=repr)
        stack = [start]
        component = set()
        while stack:
            node = stack.pop()
            if node in component:
                continue
            component.add(node)
            stack.extend(adjacency[node] - component)
        unseen -= component
        components.append(component)

    node_labels = dict(zip(candidate["nodes"], candidate["labels"], strict=True))
    label_components = defaultdict(set)
    for component_index, component in enumerate(components):
        for node in component:
            label_components[node_labels[node]].add(component_index)
    no_cluster_mixes_components = all(len(values) == 1 for values in label_components.values())
    no_component_split = all(len({node_labels[node] for node in component}) == 1 for component in components)
    return no_cluster_mixes_components and no_component_split, {
        "components": len(components),
        "clusters": len(label_components),
        "no_cluster_mixes_components": no_cluster_mixes_components,
        "no_component_split": no_component_split,
    }


def run_host_regression(env):
    def demote():
        os.setgroups([])
        os.setgid(CANDIDATE_GID)
        os.setuid(CANDIDATE_UID)

    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "networkx/algorithms/community/tests",
        "networkx/linalg/tests/test_laplacian.py",
    ]
    completed = subprocess.run(
        command,
        cwd=TESTBED,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
        preexec_fn=demote if os.getuid() == 0 else None,
    )
    return completed.returncode == 0, {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def main():
    started = time.time()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    report = {
        "task": "algobridge-0029__networkx__absorbs__scikit-learn",
        "points": [],
        "hard_gates": {},
    }
    reward = 0.0
    try:
        locks = json.loads(pathlib.Path(SOURCE_LOCK).read_text())
        cases = hidden_cases()
        payload = {"cases": cases}
        reference_env = os.environ.copy()
        reference_env["PYTHONPATH"] = "/opt/reference-host"
        reference, reference_stderr = run_json(
            [REFERENCE_PYTHON, REFERENCE_RUNNER], payload, env=reference_env, timeout=300
        )
        expected_sklearn = locks["donor"]["head_commit"]
        reference_ok = (
            reference["provenance"]["sklearn_version"] == "1.10.dev0"
            and reference["provenance"]["sklearn_file"].startswith("/opt/reference-venv/")
            and reference["provenance"]["networkx_file"].startswith("/opt/reference-host/")
        )
        report["reference"] = {
            "provenance": reference["provenance"],
            "locked_donor_commit": expected_sklearn,
            "stderr_tail": reference_stderr[-1000:],
        }
        report["hard_gates"]["locked_reference_pipeline"] = reference_ok
        if not reference_ok:
            raise RuntimeError("locked reference provenance check failed")

        synthetic_labels = [7, 7, 2, 2, 9]
        renamed_labels = [31 if value == 7 else 44 if value == 2 else 88 for value in synthetic_labels]
        label_rename_ok = math.isclose(
            adjusted_rand_index(synthetic_labels, renamed_labels),
            1.0,
            rel_tol=0.0,
            abs_tol=1e-12,
        )
        report["hard_gates"]["label_rename_invariant"] = label_rename_ok
        if not label_rename_ok:
            raise RuntimeError("label-renaming invariant self-test failed")

        findings = source_scan()
        report["hard_gates"]["forbidden_dependency_scan"] = not findings
        report["forbidden_findings"] = findings
        if findings:
            raise RuntimeError("candidate contains forbidden donor/verifier dependency")

        remove_donor()
        report["hard_gates"]["donor_removed_before_candidate"] = True
        lock_candidate_tree()
        report["hard_gates"]["candidate_tree_locked"] = True

        candidate_env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": "/testbed",
            "PYTHONNOUSERSITE": "1",
            "HOME": "/tmp/candidate-home",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
        }
        pathlib.Path(candidate_env["HOME"]).mkdir(exist_ok=True)
        os.chown(candidate_env["HOME"], CANDIDATE_UID, CANDIDATE_GID)
        isolation_probe = probe_candidate_isolation(candidate_env)
        isolation_probe_ok = all(isolation_probe.values())
        report["candidate_isolation_probe"] = isolation_probe
        report["hard_gates"]["candidate_private_paths_inaccessible"] = isolation_probe_ok
        if not isolation_probe_ok:
            raise RuntimeError(f"candidate isolation probe failed: {isolation_probe}")
        candidate, candidate_stderr = run_json(
            [sys.executable, "-I", CANDIDATE_RUNNER],
            payload,
            env=candidate_env,
            as_candidate=True,
            timeout=300,
        )
        report["candidate"] = {
            "fatal": candidate.get("fatal"),
            "networkx_file": candidate.get("networkx_file"),
            "networkx_version": candidate.get("networkx_version"),
            "isolation_checks": candidate.get("isolation_checks"),
            "stderr_tail": candidate_stderr[-1000:],
        }
        candidate_runtime_ok = (
            candidate.get("fatal") is None
            and str(candidate.get("networkx_file", "")).startswith("/testbed/")
            and candidate.get("isolation_checks")
            and all(candidate["isolation_checks"].values())
        )
        report["hard_gates"]["candidate_clean_runtime"] = candidate_runtime_ok
        if not candidate_runtime_ok:
            raise RuntimeError(f"candidate runner failed: {candidate.get('fatal')}")

        references = reference["results"]
        candidates = candidate["results"]
        if len(references) != 12 or len(candidates) != 12:
            raise RuntimeError("runner returned incorrect case count")
        for point_name, expected, actual_wrapper in zip(
            POINT_NAMES[:12], references, candidates, strict=True
        ):
            if actual_wrapper.get("ok"):
                passed, details = compare_case(expected, actual_wrapper["result"])
            else:
                passed = False
                details = {"candidate_error": actual_wrapper.get("error")}
            report["points"].append({"name": point_name, "passed": passed, **details})

        base_index = 1
        order_case = insertion_order_variant(cases[base_index])
        order_candidate, _ = run_json(
            [sys.executable, "-I", CANDIDATE_RUNNER],
            {"cases": [order_case]},
            env=candidate_env,
            as_candidate=True,
        )
        base_result = candidates[base_index]
        variant_result = order_candidate["results"][0]
        if base_result.get("ok") and variant_result.get("ok"):
            passed, details = compare_case(base_result["result"], variant_result["result"])
        else:
            passed, details = False, {"candidate_error": variant_result.get("error")}
        report["points"].append(
            {"name": POINT_NAMES[12], "passed": passed, **details}
        )

        disconnected_result = candidates[2]
        if disconnected_result.get("ok"):
            passed, details = component_invariant(cases[2], disconnected_result["result"])
        else:
            passed, details = False, {"candidate_error": disconnected_result.get("error")}
        report["points"].append(
            {"name": POINT_NAMES[13], "passed": passed, **details}
        )

        contract_ok = all(item.get("rejected") for item in candidate.get("contract_checks", []))
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
        (LOG_ROOT / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True))
        (LOG_ROOT / "reward.txt").write_text(f"{reward:.12g}\n")
        log(
            f"RESULT: {report.get('passed', 0)}/{report.get('total', len(POINT_NAMES))} "
            f"Reward={reward:.12g} hard_gates={report.get('hard_gates_passed', False)}"
        )
        for point in report.get("points", []):
            log(f"  {'PASS' if point['passed'] else 'FAIL'} {point['name']}")


if __name__ == "__main__":
    main()
