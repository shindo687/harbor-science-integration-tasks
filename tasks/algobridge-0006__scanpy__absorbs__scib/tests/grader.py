#!/usr/bin/env python3
"""Separate, dynamic differential verifier for ALGOBRIDGE-0006."""

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

from cases import hidden_cases, rename_labels


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
        r"(^|[^A-Za-z0-9_])(scib|/opt/reference|/tests|reference_runner)"
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
                findings.append(
                    f"forbidden delegation in {relative}: {match.group(0)!r}"
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
        Path("/opt/reference-runner"),
        Path("/opt/reference-host"),
        Path("/opt/reference-donor"),
        Path("/opt/pristine-host"),
        Path("/opt/wheels"),
        Path("/opt/candidate-tools"),
        Path("/opt/installed-scanpy"),
    ):
        # fuse-overlayfs can briefly report ENOTEMPTY while it retires whiteouts
        # created by a large recursive deletion.  Retry the exact, fixed path;
        # never continue into the candidate phase while reference material is
        # still reachable.
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


def candidate_call(cases, env):
    response, stderr = run_json(
        [sys.executable, CANDIDATE_RUNNER],
        {"cases": cases},
        env=env,
        candidate=True,
    )
    if response.get("fatal"):
        raise RuntimeError(f"candidate fatal: {response['fatal']}")
    if len(response.get("results", [])) != len(cases):
        raise RuntimeError("candidate returned the wrong number of results")
    return response, stderr


def max_error(left, right):
    left = np.asarray(left, dtype=np.float64)
    right = np.asarray(right, dtype=np.float64)
    if left.shape != right.shape or not np.isfinite(right).all():
        return math.inf
    return float(np.max(np.abs(left - right))) if left.size else 0.0


def compare_case(reference, candidate):
    errors = {
        "ilisi": max_error(reference["ilisi"], candidate["ilisi"]),
        "clisi": max_error(reference["clisi"], candidate["clisi"]),
        "median_ilisi": abs(reference["median_ilisi"] - candidate["median_ilisi"]),
        "median_clisi": abs(reference["median_clisi"] - candidate["median_clisi"]),
    }
    checks = {
        "ilisi": errors["ilisi"] <= 1e-6,
        "clisi": errors["clisi"] <= 1e-6,
        "median_ilisi": errors["median_ilisi"] <= 1e-7,
        "median_clisi": errors["median_clisi"] <= 1e-7,
        "effective_neighbors": reference["effective_neighbors"]
        == candidate["effective_neighbors"],
    }
    return all(checks.values()), {"checks": checks, "max_abs_errors": errors}


def reversed_storage(case):
    variant = dict(case)
    variant["name"] = case["name"] + "__reversed_csr_storage"
    encoded = case["distances"]
    data, indices, indptr = [], [], [0]
    for row in range(encoded["shape"][0]):
        start, stop = encoded["indptr"][row : row + 2]
        data.extend(reversed(encoded["data"][start:stop]))
        indices.extend(reversed(encoded["indices"][start:stop]))
        indptr.append(len(data))
    variant["distances"] = {
        "data": data,
        "indices": indices,
        "indptr": indptr,
        "shape": list(encoded["shape"]),
    }
    return variant


def scientific_invariants(base_case, base_result, env):
    renamed = rename_labels(base_case)
    storage = reversed_storage(base_case)
    single = dict(base_case)
    single["name"] = base_case["name"] + "__single_category"
    single["batch_labels"] = ["one"] * len(base_case["batch_labels"])
    single["cell_type_labels"] = ["one"] * len(base_case["cell_type_labels"])
    response, _ = candidate_call([renamed, storage, single], env)
    outputs = []
    for item in response["results"]:
        if not item.get("ok"):
            return False, {"candidate_error": item}
        outputs.append(item["result"])
    renamed_result, storage_result, single_result = outputs
    checks = {
        "batch_label_rename": max_error(base_result["ilisi"], renamed_result["ilisi"])
        <= 1e-10,
        "cell_type_label_rename": max_error(base_result["clisi"], renamed_result["clisi"])
        <= 1e-10,
        "csr_storage_order_ilisi": max_error(base_result["ilisi"], storage_result["ilisi"])
        <= 1e-10,
        "csr_storage_order_clisi": max_error(base_result["clisi"], storage_result["clisi"])
        <= 1e-10,
        "single_batch_lisi": max_error(single_result["ilisi"], np.ones(len(single_result["ilisi"])))
        <= 1e-10,
        "single_type_lisi": max_error(single_result["clisi"], np.ones(len(single_result["clisi"])))
        <= 1e-10,
    }
    return all(checks.values()), checks


def api_and_regression(env, response):
    contract = response.get("contract_checks", [])
    contract_ok = len(contract) == 7 and all(item.get("rejected") for item in contract)
    isolation = response.get("isolation_checks", {})
    isolation_ok = len(isolation) == 9 and all(isolation.values())
    api_code = r'''
import json
import scanpy as sc
from scanpy.metrics import lisi_graph_score
checks = {
    "metrics_export": callable(lisi_graph_score),
    "namespace_export": sc.metrics.lisi_graph_score is lisi_graph_score,
    "scanpy_module": lisi_graph_score.__module__.startswith("scanpy.metrics"),
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
            "/opt/regression-tests/test_metrics.py::test_confusion_matrix",
            "/opt/regression-tests/test_metrics.py::test_confusion_matrix_api",
            "/opt/regression-tests/test_metrics.py::test_correctness",
            "/opt/regression-tests/test_metrics.py::test_metrics_graph_params_errors",
        ],
        capture_output=True,
        text=True,
        env=env,
        cwd="/tmp",
        preexec_fn=_demote if os.getuid() == 0 else None,
        timeout=300,
        check=False,
    )
    passed = (
        contract_ok
        and isolation_ok
        and api.returncode == 0
        and all(api_checks.values())
        and regression.returncode == 0
    )
    return passed, {
        "contract_checks": contract,
        "isolation_checks": isolation,
        "api_checks": api_checks,
        "regression_returncode": regression.returncode,
        "regression_output": (regression.stdout + regression.stderr)[-3000:],
    }


def main():
    started = time.time()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    cases = hidden_cases()
    results = {
        case["name"]: {"passed": False, "details": {"reason": "not run"}}
        for case in cases
    }
    report = {"task": "ALGOBRIDGE-0006", "points": results}
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
            raise RuntimeError("candidate has no changed Scanpy Python files")

        log(f"reference: real Scanpy -> scIB for {len(cases)} hidden cases")
        reference_response, reference_stderr = run_json(
            [REFERENCE_PYTHON, REFERENCE_RUNNER], {"cases": cases}, timeout=600
        )
        references = reference_response["results"]
        provenance = reference_response["provenance"]
        report["reference_provenance"] = provenance
        report["reference_stderr_tail"] = reference_stderr[-2000:]
        if len(references) != len(cases):
            raise RuntimeError("reference returned the wrong number of cases")
        if not provenance["scib_file"].startswith("/opt/reference-venv/"):
            raise RuntimeError("reference did not import private locked scIB")
        if not Path(provenance["knn_graph_file"]).is_file():
            raise RuntimeError("reference did not execute a present scIB C++ binary")

        remove_reference_materials()
        lock_candidate_files()
        env = candidate_environment()
        log(f"candidate: isolated Scanpy for {len(cases)} hidden cases")
        candidate_response, candidate_stderr = candidate_call(cases, env)
        report["candidate_stderr_tail"] = candidate_stderr[-2000:]
        candidate_results = []
        for item in candidate_response["results"]:
            if not item.get("ok"):
                raise RuntimeError(f"candidate case failed: {item}")
            candidate_results.append(item["result"])

        gate_ok, gate_details = api_and_regression(env, candidate_response)
        report["api_isolation_and_host_regression"] = {
            "passed": gate_ok,
            "details": gate_details,
        }
        invariant_ok, invariant_details = scientific_invariants(
            cases[0], candidate_results[0], env
        )
        report["scientific_invariants"] = {
            "passed": invariant_ok,
            "details": invariant_details,
        }
        if not gate_ok or not invariant_ok:
            raise RuntimeError("API, isolation, regression, or invariant gate failed")

        for case, reference, candidate in zip(
            cases, references, candidate_results, strict=True
        ):
            passed, details = compare_case(reference, candidate)
            results[case["name"]] = {"passed": passed, "details": details}
    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        log(report["fatal_error"])

    passed_count = sum(item["passed"] for item in results.values())
    reward = passed_count / len(results)
    report.update(
        passed=passed_count,
        total=len(results),
        reward=reward,
        elapsed_seconds=round(time.time() - started, 3),
    )
    (LOG_ROOT / "verifier-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True)
    )
    (LOG_ROOT / "reward.txt").write_text(f"{reward:.12g}\n")
    log(f"Reward: {reward:.12g} ({passed_count}/{len(results)})")


if __name__ == "__main__":
    main()
