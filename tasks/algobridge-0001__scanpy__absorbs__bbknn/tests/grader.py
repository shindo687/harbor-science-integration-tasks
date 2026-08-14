#!/usr/bin/env python3
"""Separate dynamic differential verifier for ALGOBRIDGE-0001."""

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
from collections import Counter

import numpy as np
from scipy import sparse

from cases import as_storage_variant, hidden_cases, permutation_variant


TESTBED = Path("/testbed")
LOG_ROOT = Path("/logs/verifier")
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


def run_json(command, payload, *, env=None, candidate=False, timeout=300):
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
        r"(^|[^A-Za-z0-9_])(bbknn|/opt/reference|/tests|reference_runner)"
        r"([^A-Za-z0-9_]|$)",
        re.IGNORECASE,
    )
    locked_hashes = {}
    for line in SOURCE_HASHES.read_text().splitlines():
        digest, relative = line.split("  ", 1)
        locked_hashes[relative.removeprefix("./")] = digest
    locked_links = {}
    for line in SOURCE_LINKS.read_text().splitlines():
        relative, target = line.split("\t", 1)
        locked_links[relative] = target
    findings, changed = [], []
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
        if not path.is_file() or any(
            part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts
        ):
            continue
        data = path.read_bytes()
        if locked_hashes.get(str(relative)) == hashlib.sha256(data).hexdigest():
            continue
        changed.append(str(relative))
        if path.stat().st_size > 500_000:
            findings.append(f"oversized changed file: {relative}")
        elif path.suffix in {".so", ".o", ".a"} or b"\x00" in data:
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
            "--testbed",
            str(TESTBED),
            "--pristine",
            str(PRISTINE_HOST),
            "--output",
            str(CANDIDATE_RUNTIME),
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
        Path("/opt/reference-runner"),
        Path("/opt/reference-donor"),
        Path("/opt/pristine-host"),
        Path("/opt/wheels"),
        Path("/opt/candidate-tools"),
        Path("/opt/installed-scanpy"),
    ):
        for attempt in range(5):
            if not path.exists():
                break
            try:
                shutil.rmtree(path)
            except OSError:
                if attempt == 4:
                    raise
                time.sleep(0.2 * (attempt + 1))
        if path.exists():
            raise RuntimeError(f"failed to remove private verifier material: {path}")


def lock_candidate_files():
    for path in (TESTBED, CANDIDATE_RUNTIME):
        for command in (
            ["chown", "-R", "root:root", str(path)],
            ["chmod", "-R", "a-w", str(path)],
        ):
            completed = subprocess.run(command, capture_output=True, text=True)
            if completed.returncode:
                raise RuntimeError(f"failed to lock {path}: {completed.stderr}")


def candidate_environment():
    home = Path("/tmp/candidate-home")
    home.mkdir(exist_ok=True)
    os.chown(home, CANDIDATE_UID, CANDIDATE_GID)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": str(CANDIDATE_RUNTIME),
        "PYTHONNOUSERSITE": "1",
        "NUMBA_CACHE_DIR": str(home / "numba"),
        "MPLCONFIGDIR": str(home / "matplotlib"),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "HOME": str(home),
    }


def candidate_call(cases, env, *, timeout=300):
    response, stderr = run_json(
        [sys.executable, CANDIDATE_RUNNER],
        {"cases": cases},
        env=env,
        candidate=True,
        timeout=timeout,
    )
    if response.get("fatal"):
        raise RuntimeError(f"candidate fatal: {response['fatal']}")
    if len(response.get("results", [])) != len(cases):
        raise RuntimeError("candidate returned the wrong number of results")
    return response, stderr


def decode_csr(encoded):
    return sparse.csr_matrix(
        (
            np.asarray(encoded["data"], dtype=np.float64),
            np.asarray(encoded["indices"], dtype=np.int64),
            np.asarray(encoded["indptr"], dtype=np.int64),
        ),
        shape=tuple(encoded["shape"]),
    )


def max_array_error(left, right):
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.shape != right.shape or not np.isfinite(right).all():
        return math.inf
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def max_sparse_error(left, right):
    left, right = decode_csr(left), decode_csr(right)
    if left.shape != right.shape or not np.isfinite(right.data).all():
        return math.inf
    difference = left - right
    return float(np.max(np.abs(difference.data))) if difference.nnz else 0.0


def neighbor_ids(result):
    ids = np.asarray(result["cell_ids"], dtype=str)
    indices = np.asarray(result["indices"], dtype=np.int64)
    return ids[indices]


def compare_case(reference, candidate, spec=None):
    distance_error = max_array_error(
        reference["neighbor_distances"], candidate["neighbor_distances"]
    )
    graph_distance_error = max_sparse_error(reference["distances"], candidate["distances"])
    connectivity_error = max_sparse_error(reference["connectivities"], candidate["connectivities"])
    metadata = candidate.get("metadata_keys", {})
    params = metadata.get("params", {})
    expected_key = spec["key_added"] if spec is not None else (
        "neighbors" if candidate.get("name") != "copy_and_custom_key" else "bb"
    )
    expected_distances_key = "distances" if expected_key == "neighbors" else f"{expected_key}_distances"
    expected_connectivities_key = "connectivities" if expected_key == "neighbors" else f"{expected_key}_connectivities"
    checks = {
        "cell_ids": candidate.get("cell_ids") == reference["cell_ids"],
        "batch_order": candidate.get("batch_order") == reference["batch_order"],
        "neighbor_ids": np.array_equal(neighbor_ids(reference), neighbor_ids(candidate)),
        "neighbor_distances": distance_error <= 1e-8,
        "distance_graph": graph_distance_error <= 1e-8,
        "connectivity_graph": connectivity_error <= 1e-6,
        "copy_contract": candidate.get("return_is_copy") == reference["return_is_copy"],
        "metadata_keys": metadata.get("distances_key") == expected_distances_key
        and metadata.get("connectivities_key") == expected_connectivities_key,
        "metadata_params": params.get("batch_key")
        == (spec or {}).get("batch_key", "batch")
        and params.get("use_rep") == (spec or {}).get("use_rep", "X_pca")
        and params.get("metric")
        == (spec or {}).get("metric", params.get("metric"))
        and params.get("neighbors_within_batch")
        == (spec or {}).get(
            "neighbors_within_batch", params.get("neighbors_within_batch")
        ),
    }
    return all(checks.values()), {
        "checks": checks,
        "max_abs_errors": {
            "neighbor_distances": distance_error,
            "distance_graph": graph_distance_error,
            "connectivities": connectivity_error,
        },
    }


def aligned_permutation_invariant(base_result, permuted_result):
    base_ids = list(base_result["cell_ids"])
    permuted_ids = list(permuted_result["cell_ids"])
    order = [permuted_ids.index(cell_id) for cell_id in base_ids]
    base_neighbor_ids = neighbor_ids(base_result)
    permuted_neighbor_ids = neighbor_ids(permuted_result)[order]
    distances_ok = max_array_error(
        base_result["neighbor_distances"],
        np.asarray(permuted_result["neighbor_distances"])[order],
    ) <= 1e-10
    base_distance = decode_csr(base_result["distances"])
    perm_distance = decode_csr(permuted_result["distances"])[order][:, order]
    base_connectivity = decode_csr(base_result["connectivities"])
    perm_connectivity = decode_csr(permuted_result["connectivities"])[order][:, order]
    checks = {
        "neighbor_ids": np.array_equal(base_neighbor_ids, permuted_neighbor_ids),
        "neighbor_distances": distances_ok,
        "distance_graph": max_sparse_error(
            encode_runtime_csr(base_distance), encode_runtime_csr(perm_distance)
        ) <= 1e-10,
        "connectivity_graph": max_sparse_error(
            encode_runtime_csr(base_connectivity), encode_runtime_csr(perm_connectivity)
        ) <= 1e-6,
    }
    return all(checks.values()), checks


def storage_invariant(base_result, storage_result):
    checks = {
        "neighbor_ids": np.array_equal(neighbor_ids(base_result), neighbor_ids(storage_result)),
        "neighbor_distances": max_array_error(
            base_result["neighbor_distances"], storage_result["neighbor_distances"]
        ) <= 1e-10,
        "distance_graph": max_sparse_error(
            base_result["distances"], storage_result["distances"]
        ) <= 1e-10,
        "connectivity_graph": max_sparse_error(
            base_result["connectivities"], storage_result["connectivities"]
        ) <= 1e-6,
    }
    return all(checks.values()), checks


def encode_runtime_csr(matrix):
    matrix = sparse.csr_matrix(matrix)
    matrix.sort_indices()
    return {
        "data": matrix.data.tolist(),
        "indices": matrix.indices.tolist(),
        "indptr": matrix.indptr.tolist(),
        "shape": list(matrix.shape),
    }


def api_and_regression(env, response):
    contract = response.get("contract_checks", [])
    contract_ok = len(contract) == 7 and all(item.get("rejected") for item in contract)
    isolation = response.get("isolation_checks", {})
    isolation_ok = len(isolation) == 7 and all(isolation.values())
    api_code = r'''
import json
import scanpy as sc
from scanpy.pp import batch_balanced_neighbors
checks = {
    "preprocessing_export": callable(batch_balanced_neighbors),
    "namespace_export": sc.pp.batch_balanced_neighbors is batch_balanced_neighbors,
    "scanpy_module": batch_balanced_neighbors.__module__.startswith("scanpy."),
}
print(json.dumps(checks, sort_keys=True))
'''
    api = subprocess.run(
        [sys.executable, "-c", api_code],
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=_demote if os.getuid() == 0 else None,
        timeout=60,
        check=False,
    )
    api_checks = json.loads(api.stdout) if api.returncode == 0 else {"error": api.stderr[-2000:]}
    regression = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--disable-warnings",
            "-p",
            "testing.scanpy._pytest",
            "--basetemp=/tmp/candidate-home/pytest-tmp",
            "-o",
            "cache_dir=/tmp/candidate-home/pytest-cache",
            "-k",
            "not test_distances_euclidean",
            "/opt/regression-tests/test_neighbors.py",
            "/opt/regression-tests/test_neighbors_key_added.py",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=_demote if os.getuid() == 0 else None,
        timeout=600,
        check=False,
    )
    passed = contract_ok and isolation_ok and api.returncode == 0 and all(api_checks.values()) and regression.returncode == 0
    return passed, {
        "contract_checks": contract,
        "isolation_checks": isolation,
        "api_checks": api_checks,
        "regression_returncode": regression.returncode,
        "regression_stdout": regression.stdout[-3000:],
        "regression_stderr": regression.stderr[-2000:],
    }


def main():
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    report_path = LOG_ROOT / "grader-results.json"
    reward_path = LOG_ROOT / "reward.txt"
    report = {"task": "ALGOBRIDGE-0001", "reward": 0.0, "fatal": None}
    try:
        cases = hidden_cases()
        log(f"[1/7] Running locked Scanpy + BBKNN reference for {len(cases)} cases")
        reference_env = os.environ.copy()
        reference_env["PYTHONPATH"] = "/opt/reference-runner:/opt/reference-donor"
        reference, reference_stderr = run_json(
            [sys.executable, REFERENCE_RUNNER],
            {"cases": cases},
            env=reference_env,
            timeout=600,
        )
        if len(reference.get("results", [])) != len(cases):
            raise RuntimeError("reference returned the wrong number of results")
        report["reference_provenance"] = reference.get("provenance", {})
        report["reference_selection_backends"] = dict(
            Counter(item["selection_backend"] for item in reference["results"])
        )
        report["reference_stderr"] = reference_stderr[-2000:]

        log("[2/7] Scanning candidate changes and materializing isolated Scanpy")
        findings, changed = source_scan()
        report["source_scan"] = {"passed": not findings, "findings": findings, "changed_files": changed}
        if findings:
            raise RuntimeError("source isolation scan failed")
        manifest, materialization = materialize_candidate()
        report["overlay_manifest"] = manifest
        report["materialization"] = materialization

        log("[3/7] Removing all private reference and donor material")
        remove_reference_materials()
        lock_candidate_files()
        env = candidate_environment()

        log("[4/7] Running candidate on hidden differential cases as UID 10001")
        candidate, candidate_stderr = candidate_call(cases, env, timeout=600)
        report["candidate_stderr"] = candidate_stderr[-3000:]
        details, passed_count = [], 0
        for case, expected, actual_item in zip(cases, reference["results"], candidate["results"], strict=True):
            if not actual_item.get("ok"):
                detail = {
                    "name": case["name"],
                    "passed": False,
                    "reference_selection_backend": expected["selection_backend"],
                    "candidate_error": actual_item.get("error"),
                }
            else:
                passed, comparison = compare_case(expected, actual_item["result"], case)
                detail = {
                    "name": case["name"],
                    "passed": passed,
                    "reference_selection_backend": expected["selection_backend"],
                    **comparison,
                }
                passed_count += int(passed)
            details.append(detail)
        report["cases"] = details
        report["passed_cases"] = passed_count
        report["total_cases"] = len(cases)

        log("[5/7] Checking row permutation and dense/sparse invariants")
        invariant_case = cases[1]
        storage_case = as_storage_variant(cases[4], sparse=False)
        invariant_response, _ = candidate_call(
            [permutation_variant(invariant_case), storage_case], env
        )
        if not invariant_response["results"][0].get("ok"):
            invariant_ok, invariant_checks = False, {"candidate_error": invariant_response["results"][0]}
        else:
            invariant_ok, invariant_checks = aligned_permutation_invariant(
                candidate["results"][1]["result"], invariant_response["results"][0]["result"]
            )
        report["permutation_invariant"] = {"passed": invariant_ok, "checks": invariant_checks}
        if not invariant_response["results"][1].get("ok"):
            storage_ok, storage_checks = False, {"candidate_error": invariant_response["results"][1]}
        else:
            storage_ok, storage_checks = storage_invariant(
                candidate["results"][4]["result"], invariant_response["results"][1]["result"]
            )
        report["dense_sparse_invariant"] = {"passed": storage_ok, "checks": storage_checks}

        log("[6/7] Running API, input-contract, isolation, and Scanpy regression gates")
        gate_ok, gates = api_and_regression(env, candidate)
        report["hard_gates"] = {"passed": gate_ok, **gates}

        log("[7/7] Computing final reward")
        hard_gates_ok = gate_ok and invariant_ok and storage_ok and bool(manifest)
        reward = passed_count / len(cases) if hard_gates_ok else 0.0
        report["hard_gates_passed"] = hard_gates_ok
        report["reward"] = reward
        reward_path.write_text(f"{reward:.12g}\n")
    except Exception as error:
        report["fatal"] = f"{type(error).__name__}: {error}"
        reward_path.write_text("0\n")
        log(report["fatal"])
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n")
    log(f"Reward: {report['reward']:.12g}")


if __name__ == "__main__":
    main()
