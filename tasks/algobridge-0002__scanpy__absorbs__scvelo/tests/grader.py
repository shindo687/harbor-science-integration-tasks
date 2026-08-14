#!/usr/bin/env python3
"""Isolated dynamic differential verifier for ALGOBRIDGE-0002."""

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
import tokenize

import numpy as np

from cases import decode_csr, hidden_cases, scale_case


TESTBED = Path("/testbed")
TESTS = Path("/tests")
LOG_ROOT = Path("/logs/verifier")
REFERENCE_HOST = Path("/opt/reference-host")
REFERENCE_DONOR = Path("/opt/reference-donor")
PRISTINE_HOST = Path("/opt/pristine-host")
REFERENCE_RUNNER = Path("/opt/reference-runner/reference_runner.py")
REFERENCE_PYTHON = "/opt/reference-venv/bin/python"
CANDIDATE_RUNNER = Path("/opt/candidate-runner/candidate_runner.py")
CANDIDATE_RUNTIME = Path("/opt/candidate-runtime")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
HOST_MANIFEST_DIGEST = "3b14b76a6a993ded5a01efa6e019b808e86b7ef9ac35eaffa445be09f026f8de"
DONOR_MANIFEST_DIGEST = "090e8b570cb87d3dffeea46ab7ea51d64a012e828c070373246905c36d1da3dc"
HOST_COMMIT = "fabadb9412c0d1cd9df9d9c2e95ac266d564ee18"
DONOR_COMMIT = "f63c0e70596ced2f1bee8cf07e8ab66037cf86b2"
ALLOWED_PREFIXES = ("src/scanpy/tools/", "tests/", "pyproject.toml")


def log(message):
    print(message, flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def demote():
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def run_json(command, payload, env, *, candidate=False, timeout=600):
    completed = subprocess.run(
        command, input=json.dumps(payload, allow_nan=False), text=True,
        capture_output=True, cwd="/tmp/candidate-home" if candidate else "/tmp",
        env=env, preexec_fn=demote if candidate and os.getuid() == 0 else None,
        timeout=timeout, check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"runner exited {completed.returncode}: stdout={completed.stdout[-3000:]} "
            f"stderr={completed.stderr[-4000:]}"
        )
    return json.loads(completed.stdout), completed.stderr


def verify_manifest(list_path, root, prefix):
    failures = []
    for line in list_path.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        if not relative.startswith(prefix):
            failures.append(f"bad path: {relative}")
            continue
        path = root / relative.removeprefix(prefix)
        if not path.is_file() or digest(path) != expected:
            failures.append(relative)
    return failures


def verify_reference_integrity():
    host = TESTS / "reference-host-files.sha256"
    donor = TESTS / "reference-donor-files.sha256"
    failures = []
    if digest(host) != HOST_MANIFEST_DIGEST:
        failures.append("host manifest identity")
    if digest(donor) != DONOR_MANIFEST_DIGEST:
        failures.append("donor manifest identity")
    failures.extend(verify_manifest(host, REFERENCE_HOST, "tests/reference/host-source/"))
    failures.extend(verify_manifest(donor, REFERENCE_DONOR, "tests/reference/donor-source/"))
    lock = json.loads((TESTS / "source-lock.json").read_text())
    if lock["host"]["commit"] != HOST_COMMIT:
        failures.append("host commit")
    if lock["donor"]["commit"] != DONOR_COMMIT:
        failures.append("donor commit")
    return failures


def normalized_tokens(path):
    tokens = []
    try:
        with path.open("rb") as handle:
            for item in tokenize.tokenize(handle.readline):
                if item.type not in {
                    tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                    tokenize.COMMENT, tokenize.STRING,
                }:
                    tokens.append(item.string)
    except (OSError, tokenize.TokenError, SyntaxError, IndentationError):
        return []
    return tokens


def donor_fragments():
    fragments = set()
    for path in REFERENCE_DONOR.rglob("*.py"):
        tokens = normalized_tokens(path)
        for size in (32, 48, 64):
            fragments.update(tuple(tokens[i:i + size]) for i in range(len(tokens)-size+1))
    return fragments


def source_scan(fragments):
    forbidden = re.compile(
        r"(?:\bimport\s+scvelo\b|\bfrom\s+scvelo\b|/opt/(?:reference|scvelo)|"
        r"/tests|reference_runner|subprocess|ctypes|cffi|socket|urllib|requests)",
        re.IGNORECASE,
    )
    findings, changed = [], []
    for path in sorted(TESTBED.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(TESTBED))
        if any(part in {".git", "__pycache__", ".pytest_cache", "scanpy.egg-info"}
               for part in path.parts):
            continue
        candidate = path.read_bytes()
        pristine = PRISTINE_HOST / relative
        if pristine.is_file() and candidate == pristine.read_bytes():
            continue
        changed.append(relative)
        if not relative.startswith(ALLOWED_PREFIXES):
            findings.append(f"changed outside allowed surface: {relative}")
        if len(candidate) > 500_000 or b"\0" in candidate:
            findings.append(f"invalid changed file: {relative}")
            continue
        text = candidate.decode("utf-8", errors="replace")
        scan_text = text
        if pristine.is_file():
            scan_text = "\n".join(
                line[1:] for line in difflib.unified_diff(
                    pristine.read_text(errors="replace").splitlines(), text.splitlines()
                ) if line.startswith("+") and not line.startswith("+++")
            )
        match = forbidden.search(scan_text)
        if match:
            findings.append(f"forbidden reference in {relative}: {match.group(0)!r}")
        if path.suffix == ".py":
            tokens = normalized_tokens(path)
            for size in (64, 48, 32):
                if any(tuple(tokens[i:i+size]) in fragments for i in range(len(tokens)-size+1)):
                    findings.append(f"donor token fragment ({size}) in {relative}")
                    break
    if not any(path.endswith("_velocity_transition.py") for path in changed):
        findings.append("missing native velocity transition module")
    return findings, changed


def materialize_candidate():
    completed = subprocess.run(
        [sys.executable, "/opt/candidate-tools/materialize_candidate.py"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"candidate materialization failed: {completed.stderr[-3000:]}")
    return (CANDIDATE_RUNTIME / "OVERLAY-MANIFEST.txt").read_text().splitlines()


def destroy_private_material():
    paths = [REFERENCE_HOST, REFERENCE_DONOR, PRISTINE_HOST,
             Path("/opt/reference-runner"), Path("/opt/wheels"),
             Path("/opt/reference-venv"), Path("/opt/candidate-tools"),
             Path("/opt/installed-scanpy")]
    for path in paths:
        if path.exists():
            shutil.rmtree(path)
    if any(path.exists() for path in paths):
        raise RuntimeError("private material deletion failed")


def lock_candidate():
    for path in (TESTBED, CANDIDATE_RUNTIME):
        subprocess.run(["chown", "-R", "root:root", str(path)], check=True)
        subprocess.run(["chmod", "-R", "a-w", str(path)], check=True)


def reference_env():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/reference-host/src:/opt/reference-donor:/opt/reference-runner:/tests",
        "PYTHONNOUSERSITE": "1", "HOME": "/tmp", "MPLBACKEND": "Agg",
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
    }


def candidate_env():
    home = Path("/tmp/candidate-home")
    home.mkdir(exist_ok=True)
    os.chown(home, CANDIDATE_UID, CANDIDATE_GID)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/candidate-runtime:/opt/candidate-runner",
        "PYTHONNOUSERSITE": "1", "HOME": str(home), "TMPDIR": str(home),
        "MPLBACKEND": "Agg", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
    }


def csr_error(left, right):
    a, b = decode_csr(left), decode_csr(right)
    a.sort_indices(); b.sort_indices()
    support = (a.shape == b.shape and np.array_equal(a.indptr, b.indptr)
               and np.array_equal(a.indices, b.indices))
    error = None if not support else (
        float(np.max(np.abs(a.data-b.data))) if a.nnz else 0.0
    )
    return support, error


def compare_case(reference, candidate):
    details, passed = {}, True
    for key in ("positive", "negative", "transition"):
        support, error = csr_error(reference[key], candidate[key])
        details[f"{key}_support"] = support
        details[f"{key}_max_error"] = error
        passed &= support and error is not None and error <= 1e-6
    confidence_error = float(np.max(np.abs(
        np.asarray(reference["confidence"]) - np.asarray(candidate["confidence"])
    )))
    self_error = float(np.max(np.abs(
        np.asarray(reference["self_transition"]) - np.asarray(candidate["self_transition"])
    )))
    scientific = (
        np.allclose(candidate["absolute_row_sums"], 1.0, rtol=0, atol=2e-7)
        and candidate["positive_min"] >= 0
        and candidate["negative_max"] <= 0
        and candidate["support_overlap"] == 0
    )
    details.update({"confidence_max_error": confidence_error,
                    "self_transition_max_error": self_error,
                    "scientific_invariants": bool(scientific)})
    passed &= confidence_error <= 1e-7 and self_error <= 1e-7 and scientific
    return bool(passed), details


def run_regression(env):
    targets = [
        str(path) for path in (CANDIDATE_RUNTIME / "scanpy/tools").glob("test_velocity_transition.py")
    ] + [str(path) for path in (CANDIDATE_RUNTIME / "scanpy/tools/tests").glob("test_velocity_transition.py")]
    if not targets:
        return False, {"error": "candidate integration test missing"}
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--confcutdir=/tmp", *targets],
        env=env, cwd="/tmp/candidate-home", capture_output=True, text=True,
        preexec_fn=demote if os.getuid() == 0 else None, timeout=300, check=False,
    )
    return completed.returncode == 0, {"returncode": completed.returncode,
        "targets": targets, "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-2000:]}


def main():
    started = time.time()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    report = {"task": "algobridge-0002__scanpy__absorbs__scvelo",
              "hard_gates": {}, "points": []}
    reward = 0.0
    try:
        log("[1/8] verify locked source integrity")
        failures = verify_reference_integrity()
        report["hard_gates"]["locked_source_integrity"] = not failures
        report["integrity_failures"] = failures[:30]
        if failures:
            raise RuntimeError("locked source integrity failed")

        cases = hidden_cases()
        all_cases = cases + [scale_case(cases[2])]
        log("[2/8] compute fresh locked Scanpy -> locked scVelo references")
        reference, ref_stderr = run_json(
            [REFERENCE_PYTHON, str(REFERENCE_RUNNER)], {"cases": all_cases},
            reference_env(), timeout=900,
        )
        provenance = reference.get("provenance", {})
        reference_ok = (
            provenance.get("scanpy_file", "").startswith("/opt/reference-host/")
            and provenance.get("scvelo_file", "").startswith("/opt/reference-donor/")
            and provenance.get("scanpy_version") == "1.14.0.dev21+gfabadb941"
            and provenance.get("scvelo_version") == "0.3.3+locked.f63c0e7"
            and len(reference.get("results", [])) == len(all_cases)
        )
        report["hard_gates"]["locked_reference_pipeline"] = reference_ok
        report["reference_provenance"] = provenance
        report["reference_stderr_tail"] = ref_stderr[-2000:]
        if not reference_ok:
            raise RuntimeError("reference provenance failed")

        log("[3/8] scan candidate changes and donor-token overlap")
        fragments = donor_fragments()
        findings, changed = source_scan(fragments)
        report["hard_gates"]["clean_room_source_scan"] = not findings
        report["source_scan"] = {"findings": findings, "changed_files": changed,
                                 "donor_fragments": len(fragments)}
        if findings:
            raise RuntimeError("candidate source scan failed")

        log("[4/8] materialize candidate, delete private references, lock tree")
        overlay = materialize_candidate()
        destroy_private_material()
        lock_candidate()
        env = candidate_env()

        log("[5/8] run candidate as uid 10001")
        candidate, candidate_stderr = run_json(
            [sys.executable, str(CANDIDATE_RUNNER)], {"cases": all_cases}, env,
            candidate=True, timeout=600,
        )
        isolation = candidate.get("isolation_checks", {})
        isolation_ok = bool(isolation) and all(isolation.values())
        report["hard_gates"]["candidate_isolation"] = isolation_ok
        report["candidate_isolation"] = isolation
        report["candidate_stderr_tail"] = candidate_stderr[-2000:]
        if not isolation_ok or candidate.get("fatal"):
            raise RuntimeError(f"candidate isolation/runtime failed: {candidate.get('fatal')}")

        contract = candidate.get("contract_checks", [])
        contract_ok = (len(contract) == 9 and all(item.get("rejected") for item in contract)
                       and candidate.get("copy_semantics") is True
                       and any(path.endswith("_velocity_transition.py") for path in overlay))
        report["hard_gates"]["api_contract"] = contract_ok
        report["candidate_contract"] = {"checks": contract,
                                         "copy_semantics": candidate.get("copy_semantics"),
                                         "overlay": overlay}
        if not contract_ok:
            raise RuntimeError("candidate API contract failed")

        log("[6/8] compare 15 hidden fixtures")
        references = reference["results"]
        candidates = candidate.get("results", [])
        if len(candidates) != len(all_cases):
            raise RuntimeError("candidate result count mismatch")
        for index, spec in enumerate(cases):
            if not candidates[index].get("ok"):
                passed, details = False, {"error": candidates[index].get("error")}
            else:
                passed, details = compare_case(references[index], candidates[index]["result"])
            report["points"].append({"name": spec["name"], "passed": passed,
                                      "details": details})

        # Replace the third fixture's point with an explicit physical scaling gate.
        scaled_ref = references[-1]
        scaled_candidate = candidates[-1]
        scale_ok = scaled_candidate.get("ok", False)
        scale_details = {}
        if scale_ok:
            original = candidates[2]["result"]
            scaled = scaled_candidate["result"]
            for key in ("positive", "negative", "transition"):
                support, error = csr_error(original[key], scaled[key])
                scale_details[f"{key}_support"] = support
                scale_details[f"{key}_max_error"] = error
                scale_ok &= support and error is not None and error <= 2e-6
            donor_pass, donor_details = compare_case(scaled_ref, scaled)
            scale_ok &= donor_pass
            scale_details["scaled_reference"] = donor_details
        report["points"][2] = {"name": "global_expression_scaling_invariance",
                                "passed": bool(scale_ok), "details": scale_details}

        log("[7/8] run candidate-authored regression")
        regression_ok, regression = run_regression(env)
        report["hard_gates"]["candidate_regression"] = regression_ok
        report["candidate_regression"] = regression
        if not regression_ok:
            raise RuntimeError("candidate regression failed")

        log("[8/8] score")
        all_gates = all(report["hard_gates"].values())
        passed_count = sum(item["passed"] for item in report["points"])
        reward = passed_count / 15 if all_gates else 0.0
        report["summary"] = {"passed": passed_count, "total": 15,
                             "reward": reward, "all_hard_gates": all_gates}
    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        report.setdefault("summary", {"passed": 0, "total": 15, "reward": 0.0})
        reward = 0.0
    report["elapsed_seconds"] = time.time() - started
    (LOG_ROOT / "verifier-report.json").write_text(json.dumps(report, indent=2, allow_nan=False))
    (LOG_ROOT / "reward.txt").write_text(f"{reward:.12g}\n")
    print(json.dumps(report["summary"], allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
