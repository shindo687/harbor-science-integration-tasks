#!/usr/bin/env python3
"""Separate differential verifier for ALGOBRIDGE-0020."""

from __future__ import annotations

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

from cases import hidden_cases, invalid_cases, public_cases, transformed_pairs
from reference_runner import calculate, validate


TASK_ID = "ALGOBRIDGE-0020"
REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-boltztrap2")
ARCHIVES = Path("/opt/source-archives")
MODULE = Path("PP/src/transport_moments.f90")
DRIVER = Path("/opt/candidate-runner/transport_driver.f90")
CANDIDATE_RUNNER = Path("/opt/candidate-runner/candidate_runner.py")

EXPECTED_ARCHIVES = {
    "host-source.tar.gz": "ece7507b819fcf69d46caf31e430565066804e805e8446a0cd37fe83dd7b4c38",
    "donor-source.tar.gz": "0578bc1c58380ad9ad7d8d47bef7616bbd6c5146ad14ad1af836a4122ac0988b",
}
EXPECTED_DONOR_FILES = {
    "BoltzTraP2/bandlib.py": "9cb1a30a1fb572188bbcaa9b0f16e48dcd6d0e75e79bf56f04b24ca35d2a362f",
    "BoltzTraP2/fd.py": "bf553bb3493ea9e2eb73373d5a9bb7ae87b7e93ce51128320c48e1649bba7e24",
    "BoltzTraP2/units.py": "32acfad6e996c0419209493ed9fe85bcc8a6701d7d73d636fe7252f1f670351b",
}
FORBIDDEN = re.compile(
    r"boltz\s*trap|execute_command_line|iso_c_binding|\bsystem\b|"
    r"\bopen\s*\(|\bread\s*\(|\bwrite\s*\(|\binclude\b|"
    r"subprocess|python|socket|curl|wget|/tests\b|/opt\b|dlopen|dlsym",
    re.IGNORECASE,
)
TOKEN = re.compile(
    r"[A-Za-z_][A-Za-z_0-9]*|(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][+-]?\d+)?|\S"
)


def write_report(report, reward):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["reward"] = float(reward)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    REWARD.write_text(f"{float(reward):.10f}\n")


def fail(reason, report=None):
    report = {} if report is None else report
    report.update({"task": TASK_ID, "status": "hard_gate_failed", "reason": reason})
    write_report(report, 0.0)
    raise SystemExit(0)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ignored(relative):
    return (
        any(part in {".git", "__pycache__", ".pytest_cache"} for part in relative.parts)
        or relative.suffix in {".pyc", ".pyo"}
    )


def manifest(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if path.is_symlink():
            result[str(relative)] = "SYMLINK:" + os.readlink(path)
        elif path.is_file():
            result[str(relative)] = sha256(path)
    return result


def normalized_tokens(path):
    text = path.read_text(encoding="utf-8", errors="strict")
    text = re.sub(r"!.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"#.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"(['\"])(?:\\.|(?!\1).)*\1", " STRING ", text)
    return [value.lower() for value in TOKEN.findall(text)]


def donor_fragments():
    fragments = {64: set(), 96: set()}
    for relative in EXPECTED_DONOR_FILES:
        tokens = normalized_tokens(DONOR / relative)
        for size in fragments:
            fragments[size].update(
                tuple(tokens[index:index + size])
                for index in range(max(0, len(tokens) - size + 1))
            )
    return fragments


def reference_integrity():
    for name, expected in EXPECTED_ARCHIVES.items():
        path = ARCHIVES / name
        if not path.is_file() or sha256(path) != expected:
            return False, f"reference archive mismatch: {name}"
    for relative, expected in EXPECTED_DONOR_FILES.items():
        path = DONOR / relative
        if not path.is_file() or sha256(path) != expected:
            return False, f"locked donor file mismatch: {relative}"
    if not str(Path(sys.modules["BoltzTraP2.bandlib"].__file__).resolve()).startswith(
        str(DONOR.resolve()) + "/"
    ):
        return False, "BoltzTraP2 was not imported from the locked donor tree"
    return True, {
        "host_archive_sha256": EXPECTED_ARCHIVES["host-source.tar.gz"],
        "donor_archive_sha256": EXPECTED_ARCHIVES["donor-source.tar.gz"],
        "entry_points": ["BTPDOS", "fermiintegrals", "calc_Onsager_coefficients"],
    }


def source_policy():
    pristine = manifest(PRISTINE)
    candidate = manifest(TESTBED)
    missing = sorted(set(pristine) - set(candidate))
    changed = sorted(
        name for name in set(pristine) & set(candidate)
        if pristine[name] != candidate[name]
    )
    added = sorted(set(candidate) - set(pristine))
    if missing:
        return False, f"locked host files removed: {missing[:5]}"
    if changed:
        return False, f"locked host files changed: {changed[:5]}"
    if added != [str(MODULE)]:
        return False, f"expected only {MODULE}; found added files {added[:8]}"
    source = TESTBED / MODULE
    if not source.is_file():
        return False, f"missing {MODULE}"
    if source.stat().st_size > 100_000:
        return False, "candidate implementation exceeds 100000 bytes"
    try:
        text = source.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "candidate implementation is not UTF-8"
    if FORBIDDEN.search(text):
        return False, "candidate uses a forbidden dependency, I/O, or execution primitive"
    lower = text.lower()
    if "module transport_moments_module" not in lower or \
            "subroutine compute_transport_moments" not in lower:
        return False, "required Fortran module/subroutine is missing"
    for match in re.finditer(r"^\s*use\b([^\n]*)", text, re.IGNORECASE | re.MULTILINE):
        line = match.group(0).lower()
        if "iso_fortran_env" not in line and "ieee_arithmetic" not in line:
            return False, f"non-intrinsic module dependency is forbidden: {line.strip()}"
    numeric_literals = re.findall(
        r"(?<![A-Za-z_])(?:\d+\.\d*|\.\d+|\d+)(?:[EeDd][+-]?\d+)?",
        text,
    )
    if len(numeric_literals) > 800:
        return False, "candidate contains too many numeric literals"
    tokens = normalized_tokens(source)
    fragments = donor_fragments()
    for size in (96, 64):
        for index in range(max(0, len(tokens) - size + 1)):
            if tuple(tokens[index:index + size]) in fragments[size]:
                return False, f"candidate contains a normalized donor fragment ({size} tokens)"
    return True, {
        "added": added,
        "module_sha256": sha256(source),
        "module_bytes": source.stat().st_size,
        "numeric_literals": len(numeric_literals),
        "donor_fragment_scan": "pass (64/96 normalized tokens)",
    }


def reference_matrix(cases):
    outputs = []
    hashes = []
    for case in cases:
        first = calculate(case)
        second = calculate(case)
        encoded_first = json.dumps(first, sort_keys=True, separators=(",", ":"), allow_nan=False)
        encoded_second = json.dumps(second, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if encoded_first != encoded_second:
            raise RuntimeError(f"reference is nondeterministic for {case['name']}")
        outputs.append(first)
        hashes.append(hashlib.sha256(encoded_first.encode()).hexdigest())
    return outputs, hashes


def freeze_candidate_artifact():
    subprocess.run(["chown", "-R", "root:root", str(TESTBED)], check=True)
    for path in [TESTBED, *TESTBED.rglob("*")]:
        if path.is_symlink():
            continue
        mode = path.stat().st_mode
        path.chmod(mode & ~0o222)
    Path("/tmp/candidate-home").mkdir(mode=0o700, exist_ok=True)
    subprocess.run(["chown", "10001:10001", "/tmp/candidate-home"], check=True)
    Path("/tests").chmod(0o700)
    DONOR.chmod(0o700)
    ARCHIVES.chmod(0o700)


def isolation_probe():
    command = [
        "setpriv", "--reuid=10001", "--regid=10001", "--clear-groups",
        "--no-new-privs", "sh", "-c",
        "test ! -r /tests/grader.py && "
        "test ! -r /opt/reference-boltztrap2/BoltzTraP2/bandlib.py && "
        "test ! -w /testbed/PP/src/transport_moments.f90",
    ]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError("candidate isolation probe failed")


def run_candidate_batch(cases, timeout=300):
    environment = {
        "HOME": "/tmp/candidate-home",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "LC_ALL": "C.UTF-8",
    }
    command = [
        "setpriv", "--reuid=10001", "--regid=10001", "--clear-groups",
        "--no-new-privs", "python3", str(CANDIDATE_RUNNER),
        "--testbed", str(TESTBED), "--driver", str(DRIVER),
    ]
    completed = subprocess.run(
        command,
        input=json.dumps({"cases": cases}, allow_nan=True),
        text=True,
        capture_output=True,
        env=environment,
        timeout=timeout,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"candidate batch failed ({completed.returncode}): "
            + completed.stderr[-5000:]
        )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("candidate batch emitted invalid JSON") from exc
    if not isinstance(result, list) or len(result) != len(cases):
        raise RuntimeError("candidate batch result length mismatch")
    return result


TOLERANCES = {
    "electron_count": (2e-8, 2e-11),
    "carrier_density_cm3": (2e-8, 1e9),
    "L0": (2e-8, 1e-14),
    "L1": (2e-8, 1e-16),
    "L2": (2e-8, 1e-18),
    "sigma_over_tau_S_m_s": (2e-8, 1e5),
    "seebeck_V_K": (1e-6, 1e-10),
    "kappa_over_tau_W_m_K_s": (1e-6, 100.0),
}


def compare_case(expected, candidate):
    differences = {}
    for key, (rtol, atol) in TOLERANCES.items():
        left = np.asarray(expected.get(key), dtype=float)
        right = np.asarray(candidate.get(key), dtype=float)
        if left.shape != right.shape:
            return False, f"shape mismatch for {key}: {right.shape} != {left.shape}", differences
        if not np.all(np.isfinite(right)):
            return False, f"non-finite candidate values in {key}", differences
        absolute = float(np.max(np.abs(left - right))) if left.size else 0.0
        scale = max(float(np.max(np.abs(left))) if left.size else 0.0, atol)
        relative = absolute / scale
        differences[key] = {"max_abs": absolute, "scaled_relative": relative}
        if not np.allclose(left, right, rtol=rtol, atol=atol):
            return False, f"numeric mismatch for {key}", differences
    sigma = np.asarray(candidate["sigma_over_tau_S_m_s"], dtype=float)
    for matrix in sigma.reshape((-1, 3, 3)):
        scale = max(float(np.max(np.abs(matrix))), 1.0)
        if not np.allclose(matrix, matrix.T, rtol=1e-9, atol=scale * 1e-12):
            return False, "conductivity is not symmetric", differences
        if float(np.min(np.linalg.eigvalsh(0.5 * (matrix + matrix.T)))) < -scale * 1e-9:
            return False, "conductivity is not positive semidefinite", differences
    return True, "match", differences


def compare_pair(left, right):
    for key, (rtol, atol) in TOLERANCES.items():
        if not np.allclose(left[key], right[key], rtol=rtol, atol=atol):
            return False, key
    return True, "all outputs"


def main():
    report = {"task": TASK_ID, "hard_gates": {}}
    ok, detail = reference_integrity()
    if not ok:
        fail(detail, report)
    report["hard_gates"]["reference_integrity"] = detail

    ok, detail = source_policy()
    if not ok:
        fail(detail, report)
    report["hard_gates"]["source_policy"] = detail

    visible = public_cases()
    hidden = hidden_cases()
    pairs = transformed_pairs()
    transformed = [case for pair in pairs for case in pair]
    all_valid = visible + hidden + transformed
    try:
        expected, hashes = reference_matrix(all_valid)
    except Exception as exc:
        fail(f"real reference execution failed: {exc}", report)
    report["hard_gates"]["real_reference"] = {
        "status": "pass",
        "pipeline": "unchanged BTPDOS -> fermiintegrals -> calc_Onsager_coefficients",
        "executions": len(all_valid) * 2,
        "distinct_output_hashes": len(set(hashes)),
    }

    freeze_candidate_artifact()
    try:
        isolation_probe()
    except Exception as exc:
        fail(str(exc), report)
    report["hard_gates"]["candidate_isolation"] = {
        "uid": 10001,
        "testbed": "read-only",
        "tests": "unreadable",
        "donor": "unreadable and absent from PYTHONPATH",
        "network": "disabled by Harbor",
    }

    try:
        candidate_results = run_candidate_batch(all_valid)
    except Exception as exc:
        fail(str(exc), report)

    public_results = []
    hidden_results = []
    for index, case in enumerate(visible + hidden):
        item = candidate_results[index]
        if not item.get("ok"):
            result = {"name": case["name"], "pass": False, "detail": item.get("error", "error")}
        else:
            passed, detail, differences = compare_case(expected[index], item["output"])
            result = {
                "name": case["name"], "pass": passed, "detail": detail,
                "max_errors": differences,
            }
        if index < len(visible):
            public_results.append(result)
        else:
            hidden_results.append(result)
    if not all(item["pass"] for item in public_results):
        report["public_cases"] = public_results
        fail("one or more public examples failed", report)
    report["hard_gates"]["public_examples"] = {
        "passed": len(public_results), "total": len(public_results)
    }

    invalid = invalid_cases()
    try:
        invalid_results = run_candidate_batch(invalid)
    except Exception as exc:
        fail(f"invalid-input batch failed before per-case rejection: {exc}", report)
    invalid_report = []
    for case, item in zip(invalid, invalid_results):
        rejected = not item.get("ok")
        invalid_report.append({
            "name": case["name"], "pass": rejected,
            "detail": item.get("error", "candidate accepted malformed input")[:300],
        })
    if not all(item["pass"] for item in invalid_report):
        report["invalid_cases"] = invalid_report
        fail("candidate accepted malformed input", report)
    report["hard_gates"]["invalid_inputs"] = {
        "passed": len(invalid_report), "total": len(invalid_report)
    }

    pair_report = []
    pair_offset = len(visible) + len(hidden)
    for pair_index, pair in enumerate(pairs):
        left_item = candidate_results[pair_offset + 2 * pair_index]
        right_item = candidate_results[pair_offset + 2 * pair_index + 1]
        if not left_item.get("ok") or not right_item.get("ok"):
            passed, detail = False, "candidate failed a metamorphic case"
        else:
            passed, detail = compare_pair(left_item["output"], right_item["output"])
        pair_report.append({"name": pair[1]["name"], "pass": passed, "detail": detail})
    if not all(item["pass"] for item in pair_report):
        report["metamorphic_cases"] = pair_report
        fail("scientific metamorphic invariant failed", report)
    report["hard_gates"]["metamorphic_invariants"] = pair_report

    passed = sum(item["pass"] for item in hidden_results)
    reward = passed / len(hidden_results)
    report.update({
        "status": "accepted" if passed == len(hidden_results) else "scored",
        "public_cases": public_results,
        "hidden_cases": hidden_results,
        "invalid_cases": invalid_report,
        "metamorphic_cases": pair_report,
        "passed": passed,
        "total": len(hidden_results),
    })
    write_report(report, reward)
    print(f"{TASK_ID}: {passed}/{len(hidden_results)}, reward={reward:.6f}")


if __name__ == "__main__":
    main()
