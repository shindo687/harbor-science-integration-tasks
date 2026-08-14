#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0017."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import site
import subprocess
import sys
import tempfile

from cases import hidden_cases, invalid_cases


TESTBED = Path("/testbed")
TESTS = Path("/tests")
LOG_ROOT = Path("/logs/verifier")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-donor")
REFERENCE_SOURCE = Path("/opt/reference-gromacs")
REFERENCE_BUILD = Path("/opt/reference-gromacs-build")
REFERENCE_RUNNER = Path("/opt/reference-runner/reference_runner.py")
CANDIDATE_RUNNER = Path("/opt/candidate-runner/candidate_runner.py")
CANDIDATE_BUILD = Path("/opt/candidate-build")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001

HOST_SHA256 = "30bbdf6a344cf1958964bbdf9deb9844f64354c7853eb6e03acc1e0f41ceaec1"
DONOR_SHA256 = "d0e815a1bc88912cb0cb9c64bdb2ffc75eaec6f5225e79bd016acd5cbcf60a17"
HOST_COMMIT = "a7455395479a6eeebb8f5676ea580898c7662d21"
DONOR_COMMIT = "ed40ec3bbef03bb08938ad1a74d459b0d1ab81f7"
CPP = Path("src/gromacs/gmxana/gmx_bar_internal.cpp")
REGISTRATION = Path("src/programs/legacymodules.cpp")
EXPECTED_KEYS = {
    "delta_f", "uncertainty", "overlap", "iterations",
    "function_evaluations", "residual", "converged", "n_forward",
    "n_reverse",
}

FORBIDDEN = re.compile(
    r"(?:\bpymbar\b|\bpython(?:3)?\b|\bnumpy\b|\bscipy\b|\bnumexpr\b|"
    r"/opt/|/tests(?:/|\b)|reference[_-](?:runner|donor)|"
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
    print(f"ALGOBRIDGE-0017 hard gate: {reason}", flush=True)
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
        command,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        cwd=cwd,
        preexec_fn=demote if candidate and os.getuid() == 0 else None,
        timeout=timeout,
        check=False,
    )


def run_json(command, payload, *, env, candidate=False, timeout=900):
    completed = run(
        command,
        input_text=json.dumps(payload, allow_nan=False),
        env=env,
        cwd="/tmp/candidate-home" if candidate else "/tmp",
        candidate=candidate,
        timeout=timeout,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"runner failed ({completed.returncode}): "
            f"stdout={completed.stdout[-2000:]} stderr={completed.stderr[-3000:]}"
        )
    try:
        return json.loads(completed.stdout), completed.stderr
    except json.JSONDecodeError as error:
        raise RuntimeError(f"runner returned invalid JSON: {completed.stdout[-2000:]}") from error


def ignored(relative):
    return any(
        part in {".git", "__pycache__", ".pytest_cache", "build", "build-public"}
        or part.startswith("cmake-build-")
        for part in relative.parts
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
    text = re.sub(r"(?:[rubfRUBF]{0,2})(?:'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\")", " ", text)
    text = re.sub(r"'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"", " ", text)
    return re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?|"
        r"==|!=|<=|>=|\*\*|&&|\|\||[-+*/%<>=]",
        text,
    )


def donor_fragments():
    fragments = set()
    relevant = [
        DONOR / "pymbar/other_estimators.py",
        DONOR / "pymbar/mbar.py",
        DONOR / "pymbar/utils.py",
    ]
    for path in relevant:
        tokens = lexical_tokens(path.read_text(errors="replace"))
        for size in (64, 96):
            fragments.update(
                tuple(tokens[index:index + size])
                for index in range(max(0, len(tokens) - size + 1))
            )
    return fragments


def verify_reference_integrity():
    findings = []
    lock = json.loads((TESTS / "source-lock.json").read_text())
    if lock["host"]["commit"] != HOST_COMMIT:
        findings.append("host commit lock mismatch")
    if lock["donor"]["commit"] != DONOR_COMMIT:
        findings.append("donor commit lock mismatch")
    archives = Path("/opt/source-archives")
    if sha256(archives / "host-source.tar.gz") != HOST_SHA256:
        findings.append("host archive digest mismatch")
    if sha256(archives / "donor-source.tar.gz") != DONOR_SHA256:
        findings.append("donor archive digest mismatch")
    required = [
        PRISTINE / "CMakeLists.txt",
        REFERENCE_SOURCE / "CMakeLists.txt",
        DONOR / "pymbar/other_estimators.py",
        REFERENCE_BUILD / "bin/gmx",
    ]
    findings.extend(f"missing locked file: {path}" for path in required if not path.is_file())
    pristine_count = len(manifest(PRISTINE))
    if pristine_count != 8124:
        findings.append(f"pristine file count is {pristine_count}, expected 8124")
    version = run([str(REFERENCE_BUILD / "bin/gmx"), "--version"], timeout=60)
    if version.returncode != 0 or "2024.6" not in version.stdout:
        findings.append("locked GROMACS binary identity failed")
    return findings


def normalize_space(text):
    return re.sub(r"\s+", " ", text).strip()


def registration_policy(candidate_path, pristine_path):
    candidate = candidate_path.read_text(errors="replace")
    pristine = pristine_path.read_text(errors="replace")
    declaration = re.compile(
        r"\s*int\s+gmx_bar_internal\s*\(\s*int\s+argc\s*,\s*char\s*\*\s*argv\s*\[\s*\]\s*\)\s*;\s*"
    )
    registration = re.compile(
        r"\s*registerModule\s*\(\s*manager\s*,\s*&gmx_bar_internal\s*,\s*"
        r"\"bar-internal\"\s*,\s*\"[^\"\n]{1,200}\"\s*\)\s*;\s*"
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
    if not re.search(r"\bint\s+gmx_bar_internal\s*\(", cpp_text):
        return False, "native module does not define gmx_bar_internal"
    wiring_ok, wiring_detail = registration_policy(
        TESTBED / REGISTRATION, PRISTINE / REGISTRATION
    )
    if not wiring_ok:
        return False, wiring_detail
    tokens = lexical_tokens(cpp_text)
    for size in (96, 64):
        if any(
            tuple(tokens[index:index + size]) in fragments
            for index in range(max(0, len(tokens) - size + 1))
        ):
            return False, f"normalized donor fragment detected ({size} tokens)"
    return True, {
        "added": added,
        "changed": changed,
        "module_sha256": sha256(cpp),
        "module_bytes": cpp.stat().st_size,
        "registration": wiring_detail,
        "donor_fragment_scan": "pass (64/96 lexical tokens)",
    }


def reference_environment():
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "PYTHONPATH": "/opt/reference-donor:/tests",
        "PYTHONNOUSERSITE": "1",
        "PYMBAR_DISABLE_JAX": "1",
        "REFERENCE_GMX": str(REFERENCE_BUILD / "bin/gmx"),
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
        "HOME": "/tmp",
    }


def destroy_reference_material():
    targets = [
        PRISTINE, DONOR, REFERENCE_SOURCE, REFERENCE_BUILD,
        Path("/opt/reference-runner"), Path("/opt/source-archives"),
        Path("/opt/wheels"),
    ]
    for path in targets:
        shutil.rmtree(path, ignore_errors=True)
    patterns = (
        "numpy", "numpy-*.dist-info", "numpy.libs", "scipy", "scipy-*.dist-info",
        "scipy.libs", "numexpr", "numexpr-*.dist-info",
    )
    for root_name in site.getsitepackages():
        root = Path(root_name)
        for pattern in patterns:
            for path in root.glob(pattern):
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
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
        env={**os.environ, "HOME": "/tmp"},
        timeout=1800,
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
    if linked.returncode != 0 or any(name in link_text for name in (
        "python", "pymbar", "numpy", "scipy", "numexpr",
    )):
        raise RuntimeError(f"candidate has a forbidden dynamic dependency: {link_text[-3000:]}")
    return {
        "configure_tail": (configured.stdout + configured.stderr)[-3000:],
        "build_tail": (built.stdout + built.stderr)[-3000:],
        "binary_sha256": sha256(binary),
        "ldd": linked.stdout,
    }


def candidate_environment(home):
    return {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(home),
        "PYTHONNOUSERSITE": "1",
        "CANDIDATE_GMX": str(CANDIDATE_BUILD / "bin/gmx"),
        "GMX_MAXBACKUP": "-1",
        "GMX_NO_QUOTES": "1",
        "OMP_NUM_THREADS": "1",
    }


def host_regression(env, home):
    binary = str(CANDIDATE_BUILD / "bin/gmx")
    checks = {}
    for name, command, needle in (
        ("version", [binary, "--version"], "2024.6"),
        ("commands", [binary, "-quiet", "help", "commands"], "bar-internal"),
        ("native_help", [binary, "bar-internal", "-h"], "Usage: gmx bar-internal"),
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


def log_fermi(argument):
    if argument > 0.0:
        return -argument - math.log1p(math.exp(-argument))
    return -math.log1p(math.exp(argument))


def logsum(values):
    high = max(values)
    return high + math.log(math.fsum(math.exp(value - high) for value in values))


def recomputed_residual(spec, delta):
    offset = math.log(len(spec["forward"]) / len(spec["reverse"]))
    forward = [log_fermi(offset + work - delta) for work in spec["forward"]]
    reverse = [log_fermi(-offset + work + delta) for work in spec["reverse"]]
    return abs(logsum(forward) - logsum(reverse))


def compare_case(reference, observed):
    reasons = []
    metrics = {}
    spec = reference["input"]
    expected = reference["expected"]
    if observed.get("returncode") != 0 or not observed.get("output_exists"):
        return False, ["candidate command failed"], metrics
    result = observed.get("result")
    if not isinstance(result, dict) or set(result) != EXPECTED_KEYS:
        return False, ["output JSON field contract"], metrics
    numeric = ("delta_f", "uncertainty", "overlap", "residual")
    try:
        values = {key: float(result[key]) for key in numeric}
    except (KeyError, TypeError, ValueError, OverflowError):
        return False, ["numeric output protocol"], metrics
    if not all(math.isfinite(value) for value in values.values()):
        reasons.append("nonfinite output")
    for key in ("iterations", "function_evaluations", "n_forward", "n_reverse"):
        if isinstance(result.get(key), bool) or not isinstance(result.get(key), int):
            reasons.append(f"{key} integer protocol")
    if result.get("converged") is not True:
        reasons.append("converged diagnostic")
    if result.get("n_forward") != len(spec["forward"]) or result.get("n_reverse") != len(spec["reverse"]):
        reasons.append("sample-count diagnostic")
    iterations = result.get("iterations", -1)
    evaluations = result.get("function_evaluations", -1)
    if isinstance(iterations, int) and not 1 <= iterations <= spec["maximum_iterations"]:
        reasons.append("iteration bound")
    if isinstance(evaluations, int) and not 1 <= evaluations <= spec["maximum_iterations"] + 140:
        reasons.append("function-evaluation bound")
    errors = {
        "delta_f_abs": abs(values["delta_f"] - expected["delta_f"]),
        "uncertainty_abs": abs(values["uncertainty"] - expected["uncertainty"]),
        "overlap_abs": abs(values["overlap"] - expected["overlap"]),
    }
    metrics.update(errors)
    if errors["delta_f_abs"] > 1e-9:
        reasons.append("delta_f differential")
    if errors["uncertainty_abs"] > 1e-7:
        reasons.append("uncertainty differential")
    if errors["overlap_abs"] > 2e-8:
        reasons.append("overlap differential")
    if values["uncertainty"] < 0.0 or not 0.0 <= values["overlap"] <= 1.0:
        reasons.append("uncertainty/overlap range")
    calculated = recomputed_residual(spec, values["delta_f"])
    metrics["recomputed_residual"] = calculated
    metrics["reported_residual_abs_error"] = abs(values["residual"] - calculated)
    if calculated > 1e-10:
        reasons.append("BAR equation residual")
    if abs(values["residual"] - calculated) > 1e-10:
        reasons.append("residual diagnostic consistency")
    return not reasons, sorted(set(reasons)), metrics


def close(left, right, tolerance):
    return math.isfinite(float(left)) and math.isfinite(float(right)) and abs(float(left) - float(right)) <= tolerance


def cross_invariants(results):
    failures = []
    try:
        swap = results["swap_sign_base"]
        swapped = results["swap_sign_transformed"]
        if not close(swap["delta_f"], -swapped["delta_f"], 1e-9):
            failures.append("swap/sign delta antisymmetry")
        if not close(swap["uncertainty"], swapped["uncertainty"], 1e-8):
            failures.append("swap/sign uncertainty invariance")
        if not close(swap["overlap"], swapped["overlap"], 1e-8):
            failures.append("swap/sign overlap invariance")

        base = results["energy_zero_base"]
        shifted = results["energy_zero_shifted"]
        if not close(shifted["delta_f"] - base["delta_f"], 7.25, 1e-9):
            failures.append("energy-zero delta covariance")
        if not close(base["uncertainty"], shifted["uncertainty"], 1e-8):
            failures.append("energy-zero uncertainty invariance")
        if not close(base["overlap"], shifted["overlap"], 1e-8):
            failures.append("energy-zero overlap invariance")

        replicated = results["replication_tripled"]
        original = results["replication_base"]
        if not close(original["delta_f"], replicated["delta_f"], 1e-9):
            failures.append("replication delta invariance")
        if not close(original["overlap"], replicated["overlap"], 1e-8):
            failures.append("replication overlap invariance")
        if not close(original["uncertainty"], replicated["uncertainty"] * math.sqrt(3.0), 1e-8):
            failures.append("replication uncertainty scaling")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        failures.append(f"cross-invariant protocol: {type(error).__name__}")
    return failures


def main():
    cases = hidden_cases()
    invalid = invalid_cases()
    report = {
        "task": "ALGOBRIDGE-0017",
        "reference": "locked pristine GROMACS 2024.6 analyze -> locked pymbar BAR",
        "total": len(cases),
        "hard_gates": {},
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
            [sys.executable, str(REFERENCE_RUNNER)],
            {"cases": cases},
            env=reference_environment(),
            timeout=900,
        )
        if len(reference.get("cases", [])) != len(cases):
            fail(report, "locked reference returned the wrong case count")
        for item in reference["cases"]:
            trace = item.get("gromacs_trace", {})
            if trace.get("forward", {}).get("count") != len(item["input"]["forward"]):
                fail(report, f"reference GROMACS forward trace failed for {item.get('name')}")
            if trace.get("reverse", {}).get("count") != len(item["input"]["reverse"]):
                fail(report, f"reference GROMACS reverse trace failed for {item.get('name')}")
        report["hard_gates"]["real_gromacs_pymbar_reference"] = "pass"
        report["reference_gromacs_version"] = reference.get("gromacs_version")
        report["reference_stderr_tail"] = reference_stderr[-2000:]

        destroy_reference_material()
        report["hard_gates"]["reference_removed_before_candidate_build"] = "pass"
        subprocess.run(["chown", "-R", "root:root", str(TESTBED)], check=True)
        subprocess.run(["chmod", "-R", "a+rX", str(TESTBED)], check=True)
        subprocess.run(["chmod", "-R", "a-w", str(TESTBED)], check=True)
        build_detail = build_candidate()
        report["hard_gates"]["native_gromacs_build"] = {
            "binary_sha256": build_detail["binary_sha256"],
            "ldd": build_detail["ldd"],
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

        request = [item["input"] for item in reference["cases"]] + invalid
        candidate, candidate_stderr = run_json(
            [sys.executable, str(CANDIDATE_RUNNER)],
            {"cases": request},
            env=env,
            candidate=True,
            timeout=900,
        )
        observed = candidate.get("cases", [])
        if len(observed) != len(request):
            fail(report, "candidate runner returned the wrong case count")
        report["hard_gates"]["candidate_protocol"] = "pass"
        report["candidate_stderr_tail"] = candidate_stderr[-2000:]

        invalid_observed = observed[len(cases):]
        invalid_failures = [
            expected["name"]
            for expected, got in zip(invalid, invalid_observed, strict=True)
            if got.get("returncode") == 0 or got.get("output_exists") or "result" in got
        ]
        if invalid_failures:
            fail(report, f"malformed input/CLI accepted: {invalid_failures}")
        report["hard_gates"]["invalid_input_rejection"] = {
            "passed": len(invalid), "total": len(invalid)
        }

        results = []
        passed = 0
        result_by_name = {}
        residual_failures = []
        for expected, got in zip(reference["cases"], observed[:len(cases)], strict=True):
            ok, reasons, metrics = compare_case(expected, got)
            passed += int(ok)
            results.append({
                "name": expected["name"], "passed": ok,
                "reasons": reasons, "metrics": metrics,
            })
            if "result" in got:
                result_by_name[expected["name"]] = got["result"]
            if "BAR equation residual" in reasons or "residual diagnostic consistency" in reasons:
                residual_failures.append(expected["name"])
        if residual_failures:
            fail(report, f"scientific residual hard gate failed: {residual_failures}")
        report["hard_gates"]["bar_equation_residual"] = "pass"

        invariant_failures = cross_invariants(result_by_name)
        if invariant_failures:
            fail(report, f"cross-case scientific invariants: {invariant_failures}")
        report["hard_gates"]["scientific_transform_invariants"] = "pass"

        reward = passed / len(cases)
        report.update({
            "status": "completed",
            "passed": passed,
            "failed": len(cases) - passed,
            "cases": results,
        })
        write_report(report, reward)
        print(f"ALGOBRIDGE-0017: {passed}/{len(cases)}, reward={reward:.6f}", flush=True)
    except SystemExit:
        raise
    except Exception as error:
        report["fatal_error"] = f"{type(error).__name__}: {error}"
        write_report(report, 0.0)
        print(report["fatal_error"], flush=True)


if __name__ == "__main__":
    main()
