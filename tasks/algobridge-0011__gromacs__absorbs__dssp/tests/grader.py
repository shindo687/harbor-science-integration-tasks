#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0011."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from cases import hidden_cases, invalid_cases, public_cases


TESTBED = Path("/testbed")
TESTS = Path("/tests")
LOG_ROOT = Path("/logs/verifier")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-donor")
REFERENCE_RUNNER = Path("/opt/reference-runner/reference_runner.py")
CANDIDATE_RUNNER = Path("/opt/candidate-runner/candidate_runner.py")
CANDIDATE_BUILD = Path("/opt/candidate-build")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001

HOST_SHA256 = "30bbdf6a344cf1958964bbdf9deb9844f64354c7853eb6e03acc1e0f41ceaec1"
DONOR_SHA256 = "cc632a1a67545061a44a5cc0caca995b625b34190623844ba72548eddb67c461"
RUNTIME_SHA256 = "174a3c2259313b2d9472b8b33df02d94c9611f0e61ed28b5d9b5ef03e1a95e28"
CONDA_SHA256 = "5580f0cce0c4a1cee944f25272ba5f729eff4dc88721ebf2196c646891e2190c"
HOST_COMMIT = "a7455395479a6eeebb8f5676ea580898c7662d21"
DONOR_COMMIT = "3cbec3abea5169ea8fac030d0e43d28102b128aa"
CPP = Path("src/gromacs/gmxana/gmx_dssp_internal.cpp")
REGISTRATION = Path("src/programs/legacymodules.cpp")
TOP_KEYS = {"schema", "energy_cutoff", "residue_keys", "frames"}
FRAME_KEYS = {
    "time_ps", "complete_backbone", "secondary_structure",
    "acceptor_index", "acceptor_energy", "donor_index", "donor_energy",
}
FORBIDDEN = re.compile(
    r"(?:\bmkdssp\b|\blibdssp\b|\bpython(?:3)?\b|/opt/|/tests(?:/|\b)|"
    r"reference[_-](?:runner|donor)|"
    r"\b(?:system|popen|fork|execv?|execl|spawn|dlopen|dlsym|socket|connect)\s*\(|"
    r"\b(?:curl|wget)\b|#\s*include\s*[<\"]Python\.h[>\"])",
    re.IGNORECASE,
)


def write_report(report, reward):
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    report["reward"] = float(reward)
    (LOG_ROOT / "report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    )
    (LOG_ROOT / "reward.txt").write_text(f"{float(reward):.12g}\n")


def fail(report, reason):
    report.update({"status": "hard_gate_failed", "reason": reason})
    write_report(report, 0.0)
    print(f"ALGOBRIDGE-0011 hard gate: {reason}", flush=True)
    raise SystemExit(0)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def demote():
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def run(command, *, input_text=None, env=None, cwd=None, candidate=False,
        timeout=1800):
    return subprocess.run(
        command, input=input_text, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, env=env, cwd=cwd,
        preexec_fn=demote if candidate and os.getuid() == 0 else None,
        timeout=timeout, check=False,
    )


def run_json(command, payload, *, env, candidate=False, timeout=900):
    completed = run(
        command, input_text=json.dumps(payload, allow_nan=False), env=env,
        cwd="/tmp/candidate-home" if candidate else "/tmp",
        candidate=candidate, timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"runner failed ({completed.returncode}): "
            f"stdout={completed.stdout[-1500:]} stderr={completed.stderr[-3000:]}"
        )
    try:
        return json.loads(completed.stdout), completed.stderr
    except json.JSONDecodeError as error:
        raise RuntimeError("runner returned invalid JSON") from error


def ignored(relative):
    return any(
        part in {".git", "__pycache__", ".pytest_cache", "build", "build-public"}
        or part.startswith("cmake-build-") for part in relative.parts
    ) or relative.suffix in {".pyc", ".pyo"}


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


def lexical_tokens(text):
    text = re.sub(r"/\*.*?\*/|//[^\n]*|#[^\n]*", " ", text, flags=re.DOTALL)
    text = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", " ", text)
    return re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|"
        r"==|!=|<=|>=|&&|\|\||[-+*/%<>=]", text,
    )


def donor_fragments():
    tokens = lexical_tokens((DONOR / "libdssp/src/dssp.cpp").read_text(errors="replace"))
    return {
        size: {
            tuple(tokens[index:index + size])
            for index in range(max(0, len(tokens) - size + 1))
        }
        for size in (64, 96)
    }


def verify_reference_integrity():
    findings = []
    lock = json.loads((TESTS / "source-lock.json").read_text())
    if lock["host"]["commit"] != HOST_COMMIT:
        findings.append("host commit lock mismatch")
    if lock["donor"]["commit"] != DONOR_COMMIT:
        findings.append("donor commit lock mismatch")
    archives = Path("/opt/source-archives")
    expected = {
        archives / "host-source.tar.gz": HOST_SHA256,
        archives / "donor-source.tar.gz": DONOR_SHA256,
        archives / "dssp-runtime.tar.gz": RUNTIME_SHA256,
        archives / "dssp-4.4.11-h629725b_0.conda": CONDA_SHA256,
    }
    for path, digest in expected.items():
        if not path.is_file() or sha256(path) != digest:
            findings.append(f"locked artifact mismatch: {path.name}")
    fixture_hashes = {
        "1CRN.pdb": "42199a30a0701864a2a5cc76cd7f35cc544cd0e65fbcf63e03c166543249b811",
        "1ZDD.pdb": "d9f66e70872ddfc941f11845da945561264cfe7044c7991c701638096acbd539",
        "1TEN.pdb": "5b2165e4e495d05e230c6438a8585966578fc70006ec228ac0a0d8b65d06c73c",
    }
    for name, digest in fixture_hashes.items():
        path = Path("/opt/fixtures") / name
        if not path.is_file() or sha256(path) != digest:
            findings.append(f"fixture mismatch: {name}")
    if len(manifest(PRISTINE)) != 8124:
        findings.append("pristine host file count mismatch")
    if not (DONOR / "libdssp/src/dssp.cpp").is_file():
        findings.append("locked donor source missing")
    version = run(["/opt/dssp/bin/mkdssp", "--version"],
                  env=reference_environment(), cwd="/opt/dssp/share/libcifpp", timeout=60)
    version_text = version.stdout + version.stderr
    if version.returncode != 0 or "4.4.11" not in version_text:
        findings.append("locked mkdssp identity failed")
    return findings


def normalize_space(text):
    return re.sub(r"\s+", " ", text).strip()


def registration_policy(candidate_path, pristine_path):
    candidate = candidate_path.read_text(errors="replace")
    pristine = pristine_path.read_text(errors="replace")
    declaration = re.compile(
        r"\s*int\s+gmx_dssp_internal\s*\(\s*int\s+argc\s*,\s*char\s*\*\s*argv\s*\[\s*\]\s*\)\s*;\s*"
    )
    registration = re.compile(
        r"\s*registerModule\s*\(\s*manager\s*,\s*&gmx_dssp_internal\s*,\s*"
        r"\"dssp-internal\"\s*,\s*\"[^\"\n]{1,200}\"\s*\)\s*;\s*"
    )
    if len(declaration.findall(candidate)) != 1:
        return False, "registration file must contain one forward declaration"
    if len(registration.findall(candidate)) != 1:
        return False, "registration file must contain one command registration"
    stripped = declaration.sub(" ", candidate, count=1)
    stripped = registration.sub(" ", stripped, count=1)
    if normalize_space(stripped) != normalize_space(pristine):
        return False, "registration file contains changes beyond command wiring"
    return True, "declaration and registration only"


def source_policy(fragments):
    pristine = manifest(PRISTINE)
    candidate = manifest(TESTBED)
    missing = sorted(set(pristine) - set(candidate))
    added = sorted(set(candidate) - set(pristine))
    changed = sorted(
        name for name in set(pristine) & set(candidate)
        if pristine[name] != candidate[name]
    )
    if missing:
        return False, f"locked host files removed: {missing[:5]}"
    if added != [str(CPP)]:
        return False, f"unexpected added files: {added[:8]}"
    if changed != [str(REGISTRATION)]:
        return False, f"unexpected modified files: {changed[:8]}"
    cpp = TESTBED / CPP
    if cpp.is_symlink() or not cpp.is_file() or not 1000 <= cpp.stat().st_size <= 100000:
        return False, "native module is missing, linked, or outside the size bound"
    try:
        cpp_text = cpp.read_text(encoding="utf-8")
        registration_text = (TESTBED / REGISTRATION).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "changed source must be UTF-8"
    for relative, text in ((CPP, cpp_text), (REGISTRATION, registration_text)):
        match = FORBIDDEN.search(text)
        if match:
            return False, f"forbidden dependency/execution token in {relative}: {match.group(0)!r}"
    if not re.search(r"\bint\s+gmx_dssp_internal\s*\(", cpp_text):
        return False, "native module does not define gmx_dssp_internal"
    wiring_ok, wiring_detail = registration_policy(TESTBED / REGISTRATION,
                                                    PRISTINE / REGISTRATION)
    if not wiring_ok:
        return False, wiring_detail
    tokens = lexical_tokens(cpp_text)
    for size in (96, 64):
        if any(tuple(tokens[i:i + size]) in fragments[size]
               for i in range(max(0, len(tokens) - size + 1))):
            return False, f"normalized donor fragment detected ({size} tokens)"
    return True, {
        "added": added, "changed": changed, "module_sha256": sha256(cpp),
        "module_bytes": cpp.stat().st_size, "registration": wiring_detail,
        "donor_fragment_scan": "pass (64/96 lexical tokens)",
    }


def reference_environment():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONPATH": "/tests",
        "PYTHONNOUSERSITE": "1", "HOME": "/tmp", "OMP_NUM_THREADS": "1",
    }


def destroy_reference_material():
    targets = [
        PRISTINE, DONOR, Path("/opt/reference-runner"), Path("/opt/source-archives"),
        Path("/opt/fixtures"), Path("/opt/dssp"), Path("/opt/wheels"),
    ]
    for path in targets:
        shutil.rmtree(path, ignore_errors=True)
    remaining = [str(path) for path in targets if path.exists()]
    if remaining:
        raise RuntimeError(f"reference isolation cleanup failed: {remaining}")


def cmake_command():
    return [
        "cmake", "-S", str(TESTBED), "-B", str(CANDIDATE_BUILD), "-G", "Ninja",
        "-DGMX_FFT_LIBRARY=fftpack", "-DGMX_SIMD=SSE2", "-DGMX_MPI=OFF",
        "-DGMX_THREAD_MPI=OFF", "-DGMX_OPENMP=OFF", "-DGMX_GPU=OFF",
        "-DBUILD_TESTING=OFF", "-DGMX_BUILD_UNITTESTS=OFF", "-DGMXAPI=OFF",
        "-DGMX_INSTALL_NBLIB_API=OFF", "-DGMX_BUILD_MANUAL=OFF",
        "-DGMX_EXTERNAL_BLAS=OFF", "-DGMX_EXTERNAL_LAPACK=OFF",
        "-DCMAKE_BUILD_TYPE=Release",
    ]


def build_candidate():
    configured = run(cmake_command(), env={**os.environ, "HOME": "/tmp"}, timeout=900)
    if configured.returncode != 0:
        raise RuntimeError(f"candidate CMake failed: {configured.stderr[-5000:]}")
    built = run(
        ["cmake", "--build", str(CANDIDATE_BUILD), "--target", "gmx", "-j8"],
        env={**os.environ, "HOME": "/tmp"}, timeout=1800,
    )
    if built.returncode != 0:
        raise RuntimeError(
            f"candidate build failed: stdout={built.stdout[-3000:]} stderr={built.stderr[-5000:]}"
        )
    binary = CANDIDATE_BUILD / "bin/gmx"
    if not binary.is_file():
        raise RuntimeError("candidate build did not produce bin/gmx")
    linked = run(["ldd", str(binary)], timeout=60)
    link_text = (linked.stdout + linked.stderr).lower()
    if linked.returncode != 0 or any(name in link_text for name in
                                     ("dssp", "python", "libcifpp")):
        raise RuntimeError(f"candidate has a forbidden dynamic dependency: {link_text[-3000:]}")
    return {
        "binary_sha256": sha256(binary), "ldd": linked.stdout,
        "build_tail": (built.stdout + built.stderr)[-3000:],
    }


def candidate_environment(home):
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(home),
        "TMPDIR": str(home), "PYTHONNOUSERSITE": "1",
        "CANDIDATE_GMX": str(CANDIDATE_BUILD / "bin/gmx"),
        "GMX_MAXBACKUP": "-1", "GMX_NO_QUOTES": "1", "OMP_NUM_THREADS": "1",
    }


def host_regression(env, home):
    binary = str(CANDIDATE_BUILD / "bin/gmx")
    checks = {}
    for name, command, needle in (
        ("version", [binary, "--version"], "2024.6"),
        ("commands", [binary, "-quiet", "help", "commands"], "dssp-internal"),
        ("native_help", [binary, "dssp-internal", "-h"], "Usage: gmx dssp-internal"),
        ("analyze_help", [binary, "analyze", "-h"], "gmx analyze"),
    ):
        completed = run(command, env=env, cwd=home, candidate=True, timeout=120)
        text = completed.stdout + completed.stderr
        checks[name] = {"returncode": completed.returncode, "tail": text[-600:]}
        if completed.returncode != 0 or needle not in text:
            return False, checks
    source = home / "regression.xvg"
    output = home / "regression-output.xvg"
    source.write_text("0 0.125\n1 -0.75\n2 1.5\n")
    shutil.chown(source, user=CANDIDATE_UID, group=CANDIDATE_GID)
    completed = run(
        [binary, "analyze", "-f", str(source), "-av", str(output), "-xvg", "none"],
        env=env, cwd=home, candidate=True, timeout=120,
    )
    checks["analyze_roundtrip"] = {
        "returncode": completed.returncode,
        "tail": (completed.stdout + completed.stderr)[-600:],
    }
    if completed.returncode != 0 or not output.is_file():
        return False, checks
    observed = [
        float(line.split()[1]) for line in output.read_text().splitlines()
        if line.strip() and line.lstrip()[0] not in "#@&"
    ]
    return observed == [0.125, -0.75, 1.5], checks


def matrix_protocol(value, n, *, integer):
    if not isinstance(value, list) or len(value) != n:
        return False
    for row in value:
        if not isinstance(row, list) or len(row) != 2:
            return False
        for item in row:
            if integer:
                if isinstance(item, bool) or not isinstance(item, int):
                    return False
            elif (not isinstance(item, (int, float)) or isinstance(item, bool)
                  or not math.isfinite(float(item))):
                return False
    return True


def compare_case(case, expected, observed):
    reasons = []
    metrics = {"maximum_energy_abs_error": 0.0}
    if observed.get("returncode") != 0 or not observed.get("output_exists"):
        return False, ["candidate command failed"], metrics
    result = observed.get("result")
    if not isinstance(result, dict) or set(result) != TOP_KEYS:
        return False, ["top-level output JSON contract"], metrics
    n = len(case["topology"])
    if result.get("schema") != "algobridge-gromacs-dssp-result-v1":
        reasons.append("result schema")
    if result.get("energy_cutoff") != expected.get("energy_cutoff"):
        reasons.append("energy cutoff echo")
    if result.get("residue_keys") != expected.get("residue_keys"):
        reasons.append("residue key alignment")
    frames = result.get("frames")
    expected_frames = expected.get("frames")
    if (not isinstance(frames, list) or not isinstance(expected_frames, list)
            or len(frames) != len(expected_frames)):
        return False, reasons + ["frame count"], metrics
    allowed_codes = set("HBEGITSC")
    for index, (got, want) in enumerate(zip(frames, expected_frames, strict=True)):
        prefix = f"frame {index}"
        if not isinstance(got, dict) or set(got) != FRAME_KEYS:
            reasons.append(f"{prefix} field contract")
            continue
        if got.get("time_ps") != want.get("time_ps"):
            reasons.append(f"{prefix} time")
        complete = got.get("complete_backbone")
        if (not isinstance(complete, list) or len(complete) != n
                or any(type(value) is not bool for value in complete)):
            reasons.append(f"{prefix} complete protocol")
        elif complete != want.get("complete_backbone"):
            reasons.append(f"{prefix} complete differential")
        codes = got.get("secondary_structure")
        if not isinstance(codes, str) or len(codes) != n or not set(codes) <= allowed_codes:
            reasons.append(f"{prefix} code protocol")
        elif codes != want.get("secondary_structure"):
            reasons.append(f"{prefix} code differential")
        for key in ("acceptor_index", "donor_index"):
            if not matrix_protocol(got.get(key), n, integer=True):
                reasons.append(f"{prefix} {key} protocol")
            elif got[key] != want[key]:
                reasons.append(f"{prefix} {key} differential")
        for key in ("acceptor_energy", "donor_energy"):
            if not matrix_protocol(got.get(key), n, integer=False):
                reasons.append(f"{prefix} {key} protocol")
                continue
            error = max(
                (abs(float(a) - float(b))
                 for got_row, want_row in zip(got[key], want[key], strict=True)
                 for a, b in zip(got_row, want_row, strict=True)),
                default=0.0,
            )
            metrics["maximum_energy_abs_error"] = max(
                metrics["maximum_energy_abs_error"], error)
            if error > 1e-3:
                reasons.append(f"{prefix} {key} differential")
    return not reasons, sorted(set(reasons)), metrics


def transform_invariants(results):
    failures = []
    pairs = (
        ("hidden_crambin_original", "hidden_crambin_rigid", "rigid CRN",
         ("secondary_structure",)),
        ("hidden_ten_original", "hidden_ten_rigid", "rigid TEN",
         ("secondary_structure",)),
        ("hidden_zdd_original", "hidden_zdd_pbc", "PBC ZDD",
         ("secondary_structure", "acceptor_index", "donor_index")),
    )
    try:
        for left, right, label, fields in pairs:
            a = results[left]["frames"][0]
            b = results[right]["frames"][0]
            if any(a[field] != b[field] for field in fields):
                failures.append(f"{label} structure/bond invariance")
    except (KeyError, TypeError, IndexError) as error:
        failures.append(f"invariant protocol: {type(error).__name__}")
    return failures


def main():
    public = public_cases()
    hidden = hidden_cases()
    invalid = invalid_cases()
    valid = public + hidden
    report = {
        "task": "ALGOBRIDGE-0011",
        "reference": "locked native mkdssp 4.4.11 over bounded GROMACS frames",
        "public_total": len(public), "hidden_total": len(hidden), "hard_gates": {},
    }
    try:
        integrity = verify_reference_integrity()
        if integrity:
            fail(report, f"reference integrity: {integrity}")
        report["hard_gates"]["reference_integrity"] = "pass"

        fragments = donor_fragments()
        policy_ok, policy_detail = source_policy(fragments)
        if not policy_ok:
            fail(report, f"source policy: {policy_detail}")
        report["hard_gates"]["source_policy"] = policy_detail

        reference, reference_stderr = run_json(
            [sys.executable, str(REFERENCE_RUNNER)], {"cases": valid},
            env=reference_environment(), timeout=1200,
        )
        reference_items = reference.get("cases", [])
        if len(reference_items) != len(valid):
            fail(report, "locked reference returned the wrong case count")
        errors = [item.get("name") for item in reference_items if "result" not in item]
        if errors:
            fail(report, f"locked real mkdssp failed: {errors}")
        report["hard_gates"]["real_mkdssp_reference"] = {
            "passed": len(valid), "total": len(valid),
        }
        report["reference_stderr_tail"] = reference_stderr[-1500:]

        destroy_reference_material()
        report["hard_gates"]["reference_removed_before_candidate_build"] = "pass"
        subprocess.run(["chown", "-R", "root:root", str(TESTBED)], check=True)
        subprocess.run(["chmod", "-R", "a+rX", str(TESTBED)], check=True)
        subprocess.run(["chmod", "-R", "a-w", str(TESTBED)], check=True)
        build_detail = build_candidate()
        report["hard_gates"]["native_gromacs_build"] = {
            "binary_sha256": build_detail["binary_sha256"], "ldd": build_detail["ldd"],
        }
        report["build_log_tail"] = build_detail["build_tail"]
        subprocess.run(["chown", "-R", "root:root", str(CANDIDATE_BUILD)], check=True)
        subprocess.run(["chmod", "-R", "a-w", str(CANDIDATE_BUILD)], check=True)

        home = Path("/tmp/candidate-home")
        home.mkdir(mode=0o700, exist_ok=True)
        shutil.chown(home, user=CANDIDATE_UID, group=CANDIDATE_GID)
        env = candidate_environment(home)
        regression_ok, regression = host_regression(env, home)
        if not regression_ok:
            fail(report, f"original GROMACS regression failed: {regression}")
        report["hard_gates"]["original_gromacs_regression"] = "pass"
        report["regression"] = regression

        request = valid + invalid
        candidate, candidate_stderr = run_json(
            [sys.executable, str(CANDIDATE_RUNNER)], {"cases": request}, env=env,
            candidate=True, timeout=1200,
        )
        observed = candidate.get("cases", [])
        if len(observed) != len(request):
            fail(report, "candidate runner returned the wrong case count")
        report["candidate_stderr_tail"] = candidate_stderr[-1500:]

        invalid_observed = observed[len(valid):]
        invalid_failures = [
            expected["name"] for expected, got in zip(invalid, invalid_observed, strict=True)
            if got.get("returncode") == 0 or got.get("output_exists") or "result" in got
        ]
        if invalid_failures:
            fail(report, f"malformed input/CLI accepted: {invalid_failures}")
        report["hard_gates"]["invalid_input_rejection"] = {
            "passed": len(invalid), "total": len(invalid),
        }

        case_results = []
        candidate_by_name = {}
        for case, expected_item, got in zip(valid, reference_items,
                                             observed[:len(valid)], strict=True):
            ok, reasons, metrics = compare_case(case, expected_item["result"], got)
            case_results.append({
                "name": case["name"], "passed": ok,
                "reasons": reasons, "metrics": metrics,
            })
            if isinstance(got.get("result"), dict):
                candidate_by_name[case["name"]] = got["result"]

        invariant_failures = transform_invariants(candidate_by_name)
        if invariant_failures:
            fail(report, f"scientific transform invariants: {invariant_failures}")
        report["hard_gates"]["rigid_and_pbc_invariants"] = "pass"

        public_results = case_results[:len(public)]
        hidden_results = case_results[len(public):]
        public_passed = sum(item["passed"] for item in public_results)
        hidden_passed = sum(item["passed"] for item in hidden_results)
        reward = hidden_passed / len(hidden)
        report.update({
            "status": "completed", "public_passed": public_passed,
            "hidden_passed": hidden_passed, "hidden_failed": len(hidden) - hidden_passed,
            "public_cases": public_results, "hidden_cases": hidden_results,
        })
        write_report(report, reward)
        print(
            f"ALGOBRIDGE-0011: public {public_passed}/{len(public)}, "
            f"hidden {hidden_passed}/{len(hidden)}, reward={reward:.6f}", flush=True,
        )
    except SystemExit:
        raise
    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        write_report(report, 0.0)
        print(report["fatal_error"], flush=True)


if __name__ == "__main__":
    main()
