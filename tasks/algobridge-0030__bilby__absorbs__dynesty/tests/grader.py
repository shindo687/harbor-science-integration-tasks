#!/usr/bin/env python3
"""Separate differential verifier for Bilby's native nested sampler."""

from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize

import numpy as np

from cases import numeric_cases, reparameterization_cases, workflow_case


TESTBED = pathlib.Path("/testbed")
TESTS = pathlib.Path("/tests")
REFERENCE_HOST = pathlib.Path("/opt/reference-host")
REFERENCE_DONOR = pathlib.Path("/opt/reference-donor")
PRISTINE_HOST = pathlib.Path("/opt/pristine-host")
REFERENCE_RUNNER = pathlib.Path("/opt/reference-runner/reference_runner.py")
CANDIDATE_RUNNER = pathlib.Path("/opt/candidate-runner/candidate_runner.py")
LOG_ROOT = pathlib.Path("/logs/verifier")
REWARD_PATH = LOG_ROOT / "reward.txt"
REPORT_PATH = LOG_ROOT / "verifier-report.json"
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
HOST_COMMIT = "a139afa5e0bb1879f18aed28344adec8ca6cab9b"
HOST_TREE = "758065ac767be42b55d281eb37719e08dffb0b6b"
DONOR_COMMIT = "d8affbcd18d1cb894e0c7102ba31c65794461b55"
DONOR_TREE = "dbcfbfd8b9bd24bcc11dd3375b01832478030641"
HOST_LOCK_MANIFEST = "062749fd993b907216721ee4597c16167e319ef422f29d928c3c61f81b71f2cd"
DONOR_LOCK_MANIFEST = "098784462d1fd65dc43d881402f757b181acacc15bfd5e998b99f724b96c49d5"
ALLOWED_CHANGED = {
    # setuptools-scm writes this generated module while installing the locked
    # editable Agent package. It is deterministic environment scaffolding, not
    # an Agent implementation surface.
    "bilby/_version.py",
    "bilby/core/sampler/internal_nested.py",
    "bilby/core/sampler/tests/test_internal_nested.py",
    "bilby/core/sampler/test_internal_nested.py",
    "test/core/sampler/internal_nested_test.py",
    "pyproject.toml",
}
POINT_NAMES = [case["name"] for case in numeric_cases()] + [
    "prior_reparameterization", "determinism_and_stopping",
    "scientific_invariants", "bilby_string_selected_workflow",
    "api_and_host_regression",
]


def log(message):
    print(message, flush=True)


def demote():
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_marker(stdout):
    lines = [line for line in stdout.splitlines() if line.startswith("@@RESULT@@")]
    if len(lines) != 1:
        raise RuntimeError(f"runner returned {len(lines)} result markers")
    return json.loads(lines[0].removeprefix("@@RESULT@@"))


def run_json(command, payload, env, *, candidate=False, timeout=900):
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
    return load_marker(completed.stdout), completed.stderr


def verify_manifest(list_path, root, prefix):
    failures = []
    lines = list_path.read_text(encoding="utf-8").splitlines()
    for line in lines:
        expected, relative = line.split("  ", 1)
        if not relative.startswith(prefix):
            failures.append(f"bad manifest path: {relative}")
            continue
        path = root / relative.removeprefix(prefix)
        if not path.is_file() or digest(path) != expected:
            failures.append(relative)
    return failures


def verify_reference_integrity():
    host_manifest = TESTS / "reference-host-files.sha256"
    donor_manifest = TESTS / "reference-donor-files.sha256"
    failures = []
    if digest(host_manifest) != HOST_LOCK_MANIFEST:
        failures.append("host manifest identity")
    if digest(donor_manifest) != DONOR_LOCK_MANIFEST:
        failures.append("donor manifest identity")
    failures.extend(verify_manifest(host_manifest, REFERENCE_HOST, "tests/reference/host-source/"))
    failures.extend(verify_manifest(donor_manifest, REFERENCE_DONOR, "tests/reference/donor-source/"))
    lock = json.loads((TESTS / "source-lock.json").read_text(encoding="utf-8"))
    checks = {
        "host.commit": HOST_COMMIT, "host.tree": HOST_TREE,
        "donor.commit": DONOR_COMMIT, "donor.tree": DONOR_TREE,
    }
    for dotted, expected in checks.items():
        value = lock
        for key in dotted.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value != expected:
            failures.append(f"source-lock {dotted}")
    return failures


def normalized_py_tokens(path):
    tokens = []
    try:
        with path.open("rb") as handle:
            for item in tokenize.tokenize(handle.readline):
                if item.type in {
                    tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                    tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                    tokenize.COMMENT, tokenize.STRING,
                }:
                    continue
                tokens.append(item.string)
    except (OSError, tokenize.TokenError, IndentationError, SyntaxError):
        return []
    return tokens


def donor_fragments():
    fragments = set()
    for path in REFERENCE_DONOR.rglob("*.py"):
        tokens = normalized_py_tokens(path)
        for size in (28, 40, 56):
            fragments.update(tuple(tokens[i:i + size]) for i in range(len(tokens) - size + 1))
    return fragments


def source_scan(fragments):
    findings = []
    changed = []
    forbidden = re.compile(
        r"(?:\bimport\s+dynesty\b|\bfrom\s+dynesty\b|/opt/(?:reference|dynesty)|/tests|"
        r"subprocess|ctypes|cffi|socket|urllib|requests)", re.IGNORECASE,
    )
    for path in sorted(TESTBED.rglob("*")):
        if not path.is_file():
            continue
        relative = str(path.relative_to(TESTBED))
        if any(part in {".git", "__pycache__", ".pytest_cache", "bilby.egg-info"} for part in path.parts):
            continue
        pristine = PRISTINE_HOST / relative
        candidate_bytes = path.read_bytes()
        if pristine.is_file() and candidate_bytes == pristine.read_bytes():
            continue
        changed.append(relative)
        if relative not in ALLOWED_CHANGED:
            findings.append(f"changed file outside allowed surface: {relative}")
        if relative == "bilby/_version.py":
            # Fail closed on arbitrary content despite permitting this one
            # generated build artifact.
            generated = candidate_bytes.decode("utf-8", errors="replace")
            if "2.7.0rc0+locked.a139afa5" not in generated or "ScmVersion" in generated:
                findings.append("unexpected generated bilby/_version.py")
            continue
        if len(candidate_bytes) > 500_000:
            findings.append(f"oversized changed file: {relative}")
            continue
        if b"\0" in candidate_bytes:
            findings.append(f"binary changed file: {relative}")
            continue
        text = candidate_bytes.decode("utf-8", errors="replace")
        match = forbidden.search(text)
        if match:
            findings.append(f"forbidden runtime reference in {relative}: {match.group(0)!r}")
        tokens = normalized_py_tokens(path)
        for size in (56, 40, 28):
            hit = next((i for i in range(len(tokens) - size + 1) if tuple(tokens[i:i + size]) in fragments), None)
            if hit is not None:
                findings.append(f"donor token fragment ({size}) in {relative}")
                break
    if "bilby/core/sampler/internal_nested.py" not in changed:
        findings.append("missing native implementation module")
    return findings, changed


def prepare_candidate_tree():
    # Recreate the one build-time packaging edit documented in the Agent image.
    pyproject = TESTBED / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if '"bilby.internal_nested"' not in text:
        marker = '[project.entry-points."bilby.samplers"]\n'
        text = text.replace(marker, marker + '"bilby.internal_nested" = "bilby.core.sampler.internal_nested:InternalNested"\n', 1)
        pyproject.write_text(text, encoding="utf-8")
    shutil.copytree(pathlib.Path("/opt/candidate-metadata/bilby-2.7.0.dist-info"), "/tmp/candidate-runtime/bilby-2.7.0.dist-info")
    shutil.copytree(TESTBED / "bilby", "/tmp/candidate-runtime/bilby")


def destroy_private_material():
    paths = [
        REFERENCE_HOST, REFERENCE_DONOR, PRISTINE_HOST,
        pathlib.Path("/opt/reference-runner"), pathlib.Path("/opt/reference-metadata"),
        pathlib.Path("/opt/candidate-metadata"),
        pathlib.Path("/tests"), pathlib.Path("/opt/wheels"),
    ]
    for path in paths:
        if path.exists():
            shutil.rmtree(path)
    if any(path.exists() for path in paths):
        raise RuntimeError("private reference deletion failed")


def lock_candidate_tree():
    for path in (TESTBED, pathlib.Path("/tmp/candidate-runtime")):
        subprocess.run(["chown", "-R", "root:root", str(path)], check=True)
        subprocess.run(["chmod", "-R", "a-w", str(path)], check=True)


def reference_environment():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/reference-metadata:/opt/reference-host:/opt/reference-donor/py:/opt/reference-runner",
        "PYTHONNOUSERSITE": "1", "HOME": "/tmp", "MPLBACKEND": "Agg",
        "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
    }


def candidate_environment():
    home = pathlib.Path("/tmp/candidate-home")
    home.mkdir(exist_ok=True)
    os.chown(home, CANDIDATE_UID, CANDIDATE_GID)
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/tmp/candidate-runtime:/opt/candidate-runner",
        "PYTHONNOUSERSITE": "1", "HOME": str(home), "TMPDIR": str(home),
        "MPLBACKEND": "Agg", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
    }


def compare_statistics(reference, candidate, spec):
    ndim = len(spec["bounds"])
    # Nested-sampling evidence errors are stochastic estimates. A 2.6-sigma
    # envelope covers the discontinuous plateau fixture without weakening the
    # posterior or scientific-invariant checks.
    logz_tolerance = max(0.42, 2.6 * reference["log_evidence_err"])
    mean_tolerance = 0.28 if ndim == 1 else 0.38 if ndim == 2 else 0.46
    covariance_tolerance = 0.32 if ndim == 1 else 0.45 if ndim == 2 else 0.55
    logz_error = abs(candidate["log_evidence"] - reference["log_evidence"])
    mean_error = float(np.max(np.abs(np.asarray(candidate["posterior_mean"]) - np.asarray(reference["posterior_mean"]))))
    covariance_error = float(np.max(np.abs(np.asarray(candidate["posterior_cov"]) - np.asarray(reference["posterior_cov"]))))
    scientific = (
        candidate["all_finite"] and candidate["dead_likelihood_monotonic"]
        and candidate["weights_min"] > 0 and abs(candidate["weights_sum"] - 1.0) <= 1e-10
        and candidate["unit_cube_valid"] and candidate["trace_length"] >= candidate["sample_count"] - spec["nlive"]
        and candidate["ncall"] == spec["nlive"] + candidate["niter"] * spec["walks"]
        and (
            candidate["niter"] == 0
            or math.isclose(
                candidate["trace_first_log_prior_volume"],
                -1.0 / spec["nlive"], rel_tol=0.0, abs_tol=1e-12,
            )
        )
    )
    passed = scientific and logz_error <= logz_tolerance and mean_error <= mean_tolerance and covariance_error <= covariance_tolerance
    return passed, {
        "logz_error": logz_error, "logz_tolerance": logz_tolerance,
        "mean_max_error": mean_error, "mean_tolerance": mean_tolerance,
        "covariance_max_error": covariance_error, "covariance_tolerance": covariance_tolerance,
        "scientific_contract": scientific,
    }


def run_regression(env):
    targets = [
        "/tmp/candidate-runtime/bilby/core/sampler/tests/test_internal_nested.py",
        "/tmp/candidate-runtime/bilby/core/sampler/test_internal_nested.py",
        "/tmp/candidate-runtime/test/core/sampler/internal_nested_test.py",
    ]
    existing = [target for target in targets if pathlib.Path(target).is_file()]
    if not existing:
        return False, {"error": "candidate did not add integration regression tests"}
    command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--confcutdir=/tmp"] + existing
    completed = subprocess.run(
        command, env=env, cwd="/tmp/candidate-home", text=True, capture_output=True,
        preexec_fn=demote if os.getuid() == 0 else None, timeout=300, check=False,
    )
    return completed.returncode == 0, {
        "returncode": completed.returncode, "targets": existing,
        "stdout_tail": completed.stdout[-4000:], "stderr_tail": completed.stderr[-2000:],
    }


def main():
    started = time.time()
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    report = {"task": "algobridge-0030__bilby__absorbs__dynesty", "points": [], "hard_gates": {}}
    reward = 0.0
    try:
        log("[1/8] Verify immutable Bilby and dynesty references")
        integrity_failures = verify_reference_integrity()
        report["hard_gates"]["locked_source_integrity"] = not integrity_failures
        report["integrity_failures"] = integrity_failures[:30]
        if integrity_failures:
            raise RuntimeError("locked source integrity failed")

        all_reference_cases = numeric_cases() + reparameterization_cases() + [workflow_case()]
        log("[2/8] Compute fresh original Bilby -> original dynesty references")
        reference, reference_stderr = run_json(
            [sys.executable, str(REFERENCE_RUNNER)], {"cases": all_reference_cases},
            reference_environment(), timeout=1500,
        )
        provenance = reference.get("provenance", {})
        reference_ok = (
            provenance.get("bilby_file", "").startswith("/opt/reference-host/")
            and provenance.get("dynesty_file", "").startswith("/opt/reference-donor/")
            and provenance.get("bilby_version") in {"unknown", "2.7.0+locked.a139afa5"}
            and provenance.get("dynesty_version") == "3.0.0+locked.d8affbc"
            and len(reference.get("results", [])) == len(all_reference_cases)
        )
        report["hard_gates"]["locked_reference_pipeline"] = reference_ok
        report["reference_provenance"] = provenance
        report["reference_stderr_tail"] = reference_stderr[-2000:]
        if not reference_ok:
            raise RuntimeError("reference provenance failed")

        log("[3/8] Scan candidate surface, donor imports, and copied donor fragments")
        fragments = donor_fragments()
        findings, changed = source_scan(fragments)
        report["hard_gates"]["clean_room_source_scan"] = not findings
        report["source_scan"] = {"findings": findings, "changed_files": changed, "donor_fragments": len(fragments)}
        if findings:
            raise RuntimeError("candidate source scan failed")

        log("[4/8] Materialize candidate and physically destroy all private materials")
        prepare_candidate_tree()
        destroy_private_material()
        lock_candidate_tree()

        items = [{"mode": "core", "spec": case} for case in numeric_cases()]
        items += [{"mode": "core", "spec": case} for case in reparameterization_cases()]
        stop_case = dict(numeric_cases()[0])
        stop_case.update(name="determinism_stop", seed=1433, dlogz=0.18, maxiter=4000)
        items += [
            {"mode": "core", "spec": stop_case},
            {"mode": "core", "spec": stop_case},
            {"mode": "workflow", "spec": workflow_case()},
        ]
        log("[5/8] Run candidate as isolated unprivileged UID 10001")
        candidate, candidate_stderr = run_json(
            [sys.executable, str(CANDIDATE_RUNNER)], {"items": items},
            candidate_environment(), candidate=True, timeout=1500,
        )
        report["candidate_stderr_tail"] = candidate_stderr[-3000:]
        isolation_ok = all(candidate.get("isolation", {}).values())
        contract = candidate.get("contract", {})
        contract_ok = (
            contract.get("core_signature") and contract.get("class_name")
            and contract.get("registry") and contract.get("invalid_inputs_rejected")
            and contract.get("invalid_count") == 6
        )
        report["hard_gates"]["candidate_isolation"] = isolation_ok
        report["hard_gates"]["api_contract"] = contract_ok
        report["candidate_isolation"] = candidate.get("isolation", {})
        report["candidate_contract"] = contract
        if not isolation_ok or not contract_ok or len(candidate.get("results", [])) != len(items):
            raise RuntimeError("candidate isolation/API failed")

        results = candidate["results"]
        points = []
        log("[6/8] Compare 10 statistical fixtures to dynesty")
        for index, spec in enumerate(numeric_cases()):
            actual = results[index]
            if not actual.get("ok"):
                passed, details = False, {"error": actual.get("error"), "traceback": actual.get("traceback")}
            else:
                passed, details = compare_statistics(reference["results"][index], actual["value"], spec)
            points.append({"name": spec["name"], "passed": passed, "details": details})

        offset = len(numeric_cases())
        reparam_actual = results[offset:offset + 2]
        if all(item.get("ok") for item in reparam_actual):
            left, right = (item["value"] for item in reparam_actual)
            reparam_error = abs(left["log_evidence"] - right["log_evidence"])
            reparam_ok = reparam_error <= 0.38
            reparam_details = {"log_evidence_difference": reparam_error, "tolerance": 0.38}
        else:
            reparam_ok, reparam_details = False, {"errors": [item.get("error") for item in reparam_actual]}
        points.append({"name": "prior_reparameterization", "passed": reparam_ok, "details": reparam_details})

        first, second = results[offset + 2:offset + 4]
        if first.get("ok") and second.get("ok"):
            a, b = first["value"], second["value"]
            deterministic = a == b
            stopped = a["niter"] < stop_case["maxiter"] and a["ncall"] <= stop_case.get("maxcall", 300000)
            stop_ok = deterministic and stopped
            stop_details = {"bitwise_json_deterministic": deterministic, "stopped_before_maxiter": stopped, "niter": a["niter"], "ncall": a["ncall"]}
        else:
            stop_ok, stop_details = False, {"errors": [first.get("error"), second.get("error")]}
        points.append({"name": "determinism_and_stopping", "passed": stop_ok, "details": stop_details})

        successful = [item["value"] for item in results[:offset] if item.get("ok")]
        scientific_ok = len(successful) == offset and all(
            value["all_finite"] and value["dead_likelihood_monotonic"]
            and value["weights_min"] > 0 and abs(value["weights_sum"] - 1.0) <= 1e-10
            and value["unit_cube_valid"]
            and (value["trace_length"] > 0 or value["niter"] == 0)
            for value in successful
        )
        points.append({"name": "scientific_invariants", "passed": scientific_ok, "details": {"successful_core_runs": len(successful), "required": offset}})

        workflow_actual = results[-1]
        workflow_reference = reference["results"][-1]
        if workflow_actual.get("ok"):
            value = workflow_actual["value"]
            logz_error = abs(value["log_evidence"] - workflow_reference["log_evidence"])
            mean_error = float(np.max(np.abs(np.asarray(value["posterior_mean"]) - np.asarray(workflow_reference["posterior_mean"]))))
            workflow_ok = (
                logz_error <= max(0.45, 2.5 * workflow_reference["log_evidence_err"])
                and mean_error <= 0.40 and value["weights_min"] > 0
                and abs(value["weights_sum"] - 1.0) <= 1e-10
                and value["trace_present"] and value["sampler"] in {"internalnested", "internal_nested"}
                and {"weights", "log_likelihood"} <= set(value["nested_columns"])
                and value["integration_niter"] is not None
                and value["integration_ncall"] == workflow_case()["nlive"] + value["integration_niter"] * workflow_case()["walks"]
                and (
                    value["integration_niter"] == 0
                    or math.isclose(
                        value["trace_first_log_prior_volume"],
                        -1.0 / workflow_case()["nlive"], rel_tol=0.0, abs_tol=1e-12,
                    )
                )
            )
            workflow_details = {"logz_error": logz_error, "mean_error": mean_error, "value": value}
        else:
            workflow_ok, workflow_details = False, {"error": workflow_actual.get("error"), "traceback": workflow_actual.get("traceback")}
        points.append({"name": "bilby_string_selected_workflow", "passed": workflow_ok, "details": workflow_details})

        log("[7/8] Run candidate-authored integration regressions")
        regression_ok, regression_details = run_regression(candidate_environment())
        points.append({"name": "api_and_host_regression", "passed": regression_ok, "details": regression_details})
        report["hard_gates"]["candidate_regression"] = regression_ok
        report["points"] = points

        passed_count = sum(point["passed"] for point in points)
        hard_gates_ok = all(report["hard_gates"].values())
        reward = passed_count / len(POINT_NAMES) if hard_gates_ok else 0.0
        report["summary"] = {"passed": passed_count, "total": len(POINT_NAMES), "hard_gates_ok": hard_gates_ok, "reward": reward}
        log(f"[8/8] Result: {passed_count}/{len(POINT_NAMES)}, Reward={reward:.12g}")
    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        report["summary"] = {"passed": 0, "total": len(POINT_NAMES), "reward": 0.0}
        log(f"Verifier fatal error: {type(error).__name__}: {error}")
        reward = 0.0
    finally:
        report["elapsed_seconds"] = time.time() - started
        REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        REWARD_PATH.write_text(f"{reward:.12g}\n", encoding="utf-8")


if __name__ == "__main__":
    main()
