#!/usr/bin/env python3
"""Separate, offline differential verifier for ALGOBRIDGE-0008."""

from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tarfile

from candidate_runner import run_candidate, run_invalid
from cases import PUBLIC_CASES, hidden_cases, permuted, validate_case
from reference_runner import apc, contacts, run_reference


TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host/hh-suite")
DONOR = Path("/opt/donor-source/CCMpred")
LOCK_PATH = Path("/tests/source-lock.json")
REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")


class GateFailure(RuntimeError):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_result(report: dict, reward: float) -> None:
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["reward"] = float(reward)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REWARD.write_text(f"{float(reward):.10f}\n", encoding="ascii")


def fail(reason: str, report: dict | None = None) -> None:
    payload = {} if report is None else report
    payload.update({"status": "hard_gate_failed", "reason": f"GateFailure: {reason}"})
    write_result(payload, 0.0)
    raise SystemExit(0)


def archive_members(path: Path) -> int:
    with tarfile.open(path) as archive:
        return sum(member.isfile() or member.issym() for member in archive)


def provenance(lock: dict) -> dict:
    checks: dict[str, bool] = {}
    paths = {
        "host_archive": (Path("/opt/source-archives/host-source.tar.gz"), lock["host"]["archive_sha256"], lock["host"]["archive_size"]),
        "donor_archive": (Path("/opt/source-archives/donor-source.tar.gz"), lock["donor"]["archive_sha256"], lock["donor"]["archive_size"]),
        "reference_binary": (Path("/opt/reference-ccmpred/ccmpred"), lock["reference_runtime"]["sha256"], lock["reference_runtime"]["size"]),
        "build_patch": (Path("/opt/reference-ccmpred/build-compatibility.patch"), lock["reference_runtime"]["compatibility_patch_sha256"], None),
    }
    for name, (path, expected_hash, expected_size) in paths.items():
        checks[name] = path.is_file() and sha256(path) == expected_hash
        if expected_size is not None:
            checks[name] = checks[name] and path.stat().st_size == expected_size
    checks["host_member_count"] = archive_members(paths["host_archive"][0]) == lock["host"]["archive_files"]
    checks["donor_member_count"] = archive_members(paths["donor_archive"][0]) == lock["donor"]["archive_files"]
    checks["lock_copies"] = sha256(LOCK_PATH) == sha256(Path("/opt/task-source-lock.json"))
    if not all(checks.values()):
        raise GateFailure(f"provenance check failed: {checks}")
    return checks


def all_entries(root: Path) -> dict[Path, Path]:
    return {
        path.relative_to(root): path
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }


def generated_extra(relative: Path) -> bool:
    if relative == Path("hhcontacts"):
        return True
    first = relative.parts[0] if relative.parts else ""
    return first == "build" or first.startswith("build-") or first in {".cache", "_build"}


def source_integrity(lock: dict) -> dict:
    baseline = all_entries(PRISTINE)
    candidate = all_entries(TESTBED)
    allowed_changes = {Path("src/CMakeLists.txt"), Path("src/hhcontacts.cpp")}
    missing = sorted(str(path) for path in baseline if path not in candidate)
    if missing:
        raise GateFailure(f"host files missing: {missing[:8]}")
    unexpected = sorted(
        str(path) for path in candidate
        if path not in baseline and path not in allowed_changes and not generated_extra(path)
    )
    if unexpected:
        raise GateFailure(f"unexpected files in candidate host: {unexpected[:8]}")
    for relative, original in baseline.items():
        if relative in allowed_changes:
            continue
        submitted = candidate[relative]
        if original.is_symlink() != submitted.is_symlink():
            raise GateFailure(f"file type changed: {relative}")
        if original.is_symlink():
            if os.readlink(original) != os.readlink(submitted):
                raise GateFailure(f"symlink target changed: {relative}")
        elif sha256(original) != sha256(submitted):
            raise GateFailure(f"unrelated host file changed: {relative}")

    source = TESTBED / "src/hhcontacts.cpp"
    if not source.is_file() or source.is_symlink() or source.stat().st_size > lock["candidate_contract"]["max_source_bytes"]:
        raise GateFailure("missing, linked, or oversized src/hhcontacts.cpp")
    cmake = TESTBED / "src/CMakeLists.txt"
    if not cmake.is_file() or cmake.is_symlink():
        raise GateFailure("src/CMakeLists.txt is missing or linked")
    submitted_text = cmake.read_text(encoding="utf-8")
    target = "add_executable(hhcontacts${EXE_SUFFIX} hhcontacts.cpp)\n\n"
    install = "        hhcontacts${EXE_SUFFIX}\n"
    if submitted_text.count(target) != 1 or submitted_text.count(install) != 1:
        raise GateFailure("hhcontacts is not registered and installed exactly once in CMake")
    normalized = submitted_text.replace(target, "").replace(install, "")
    baseline_cmake = (PRISTINE / "src/CMakeLists.txt").read_text(encoding="utf-8")
    if normalized != baseline_cmake:
        raise GateFailure("CMake changes exceed the bounded hhcontacts registration")
    return {"baseline_files": len(baseline), "candidate_source_bytes": source.stat().st_size}


TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z_0-9]*|(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|[^\s]")


def token_windows(text: str, width: int = 64) -> set[tuple[str, ...]]:
    tokens = TOKEN_RE.findall(re.sub(r"/\*.*?\*/|//[^\n]*", " ", text, flags=re.DOTALL))
    return {tuple(tokens[index:index + width]) for index in range(max(0, len(tokens) - width + 1))}


def source_policy() -> dict:
    source_path = TESTBED / "src/hhcontacts.cpp"
    text = source_path.read_text(encoding="utf-8", errors="replace")
    forbidden = {
        "donor include": r"#\s*include[^\n]*(?:ccmpred|conjugrad)",
        "protected path": r"/(?:opt/(?:reference-ccmpred|donor-source|pristine-host|source-archives)|tests)(?:/|\b)",
        "process execution": r"\b(?:system|popen|fork|execv|execl|posix_spawn)\s*\(",
        "dynamic loading": r"\b(?:dlopen|dlsym)\s*\(",
        "network API": r"\b(?:socket|connect|getaddrinfo|curl_easy_init)\s*\(",
    }
    hits = {name: pattern for name, pattern in forbidden.items() if re.search(pattern, text, re.IGNORECASE)}
    if hits:
        raise GateFailure(f"candidate source policy violation: {sorted(hits)}")

    donor_windows: set[tuple[str, ...]] = set()
    for path in DONOR.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".c", ".h", ".cu", ".cc", ".cpp"}:
            donor_windows.update(token_windows(path.read_text(encoding="utf-8", errors="ignore")))
    overlap = token_windows(text) & donor_windows
    if overlap:
        example = " ".join(next(iter(overlap))[:12])
        raise GateFailure(f"candidate contains a 64-token donor-source window: {example}")
    return {"forbidden_patterns": len(forbidden), "donor_windows": len(donor_windows), "overlap": 0}


def isolation_check() -> dict:
    protected = [
        "/tests", "/opt/reference-ccmpred", "/opt/donor-source",
        "/opt/pristine-host", "/opt/source-archives", "/opt/task-source-lock.json",
    ]
    script = (
        "import json,os,sys; os.setgroups([]); os.setgid(10001); os.setuid(10001); "
        "print(json.dumps({p:{'read':os.access(p,os.R_OK),'list':os.access(p,os.R_OK|os.X_OK)} "
        "for p in sys.argv[1:]}))"
    )
    completed = subprocess.run(["python3", "-c", script, *protected], text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    result = json.loads(completed.stdout)
    if any(value["read"] or value["list"] for value in result.values()):
        raise GateFailure(f"candidate UID can access protected verifier paths: {result}")
    return result


def build_candidate() -> dict:
    command = [
        "g++", "-std=c++11", "-O3", "-Wall", "-Wextra", "-pedantic",
        str(TESTBED / "src/hhcontacts.cpp"), "-o", str(TESTBED / "hhcontacts"),
    ]
    completed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=300, check=False)
    if completed.returncode != 0:
        raise GateFailure(f"candidate compilation failed: {completed.stdout[-4000:]}")
    binary = TESTBED / "hhcontacts"
    binary.chmod(0o755)
    help_run = subprocess.run([str(binary), "--help"], text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=20, check=False)
    if help_run.returncode != 0 or "--reweight-threshold" not in help_run.stdout:
        raise GateFailure("compiled hhcontacts does not expose the required CLI")
    linked = subprocess.run(["ldd", str(binary)], text=True, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, check=True).stdout
    if re.search(r"ccmpred|conjugrad", linked, re.IGNORECASE):
        raise GateFailure("candidate binary links a donor runtime")
    return {"command": command, "binary_sha256": sha256(binary), "help": "pass"}


def symmetric_zero_diagonal(matrix: list[list[float]], tolerance: float = 1e-10) -> bool:
    length = len(matrix)
    return all(
        abs(matrix[row][row]) <= tolerance and
        all(abs(matrix[row][column] - matrix[column][row]) <= tolerance for column in range(length))
        for row in range(length)
    )


def pearson(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return float("nan")
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_norm = sum((value - left_mean) ** 2 for value in left)
    right_norm = sum((value - right_mean) ** 2 for value in right)
    if left_norm <= 0.0 or right_norm <= 0.0:
        return 1.0 if all(abs(a - b) <= 1e-12 for a, b in zip(left, right)) else 0.0
    return numerator / math.sqrt(left_norm * right_norm)


def upper(matrix: list[list[float]]) -> list[float]:
    return [matrix[row][column] for row in range(len(matrix)) for column in range(row + 1, len(matrix))]


def top_pairs(matrix: list[list[float]], count: int) -> set[tuple[int, int]]:
    ranked = [
        (matrix[first][second], first + 1, second + 1)
        for first in range(len(matrix))
        for second in range(first + 5, len(matrix))
    ]
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return {(first, second) for _, first, second in ranked[:count]}


def compare(expected: dict, observed: dict) -> tuple[dict[str, bool], dict]:
    length = expected["length"]
    if observed["length"] != length or observed["sequence_count"] != expected["sequence_count"]:
        return ({key: False for key in ("raw", "apc", "top_l2", "objective")}, {"shape": False})
    raw_correlation = pearson(upper(expected["raw_score"]), upper(observed["raw_score"]))
    apc_correlation = pearson(upper(expected["apc_score"]), upper(observed["apc_score"]))
    wanted = max(1, length // 2)
    expected_top = top_pairs(expected["apc_score"], wanted)
    observed_top = top_pairs(observed["apc_score"], wanted)
    overlap = len(expected_top & observed_top) / len(expected_top)
    objective_error = abs(expected["diagnostics"]["objective"] - observed["diagnostics"]["objective"])
    components = {
        "raw": raw_correlation >= 0.999,
        "apc": apc_correlation >= 0.999,
        "top_l2": overlap >= 0.95,
        "objective": objective_error <= 1e-5,
    }
    errors = {
        "raw_correlation": raw_correlation,
        "apc_correlation": apc_correlation,
        "top_l2_overlap": overlap,
        "objective_absolute_error": objective_error,
    }
    return components, errors


def candidate_invariants(observed: dict) -> dict:
    raw = observed["raw_score"]
    corrected = observed["apc_score"]
    recomputed = apc(raw)
    apc_error = max(abs(a - b) for row_a, row_b in zip(corrected, recomputed) for a, b in zip(row_a, row_b))
    expected_contacts = contacts(corrected)
    contact_identity = [
        (item.get("i"), item.get("j")) for item in observed["top_contacts"]
    ] == [(item["i"], item["j"]) for item in expected_contacts]
    return {
        "raw_symmetric_zero_diagonal": symmetric_zero_diagonal(raw),
        "apc_symmetric_zero_diagonal": symmetric_zero_diagonal(corrected),
        "apc_formula_max_error": apc_error,
        "top_contacts_consistent": contact_identity,
    }


def row_permutation_gate(packet: dict) -> dict:
    original = run_candidate(packet)
    reordered = run_candidate(permuted(packet))
    raw_correlation = pearson(upper(original["raw_score"]), upper(reordered["raw_score"]))
    apc_correlation = pearson(upper(original["apc_score"]), upper(reordered["apc_score"]))
    objective_error = abs(original["diagnostics"]["objective"] - reordered["diagnostics"]["objective"])
    result = {
        "raw_correlation": raw_correlation,
        "apc_correlation": apc_correlation,
        "objective_absolute_error": objective_error,
        "top_l2_equal": top_pairs(original["apc_score"], max(1, original["length"] // 2)) ==
                        top_pairs(reordered["apc_score"], max(1, reordered["length"] // 2)),
    }
    if raw_correlation < 0.999999999 or apc_correlation < 0.999999999 or objective_error > 1e-8:
        raise GateFailure(f"alignment row permutation changed the result: {result}")
    return result


def main() -> None:
    report: dict = {}
    try:
        lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        report["provenance"] = provenance(lock)
        report["source_integrity"] = source_integrity(lock)
        report["source_policy"] = source_policy()
        report["isolation"] = isolation_check()
        report["build"] = build_candidate()
    except GateFailure as error:
        fail(str(error), report)
    except Exception as error:
        fail(f"setup failed: {type(error).__name__}: {error}", report)

    invalid: dict[str, bool] = {}
    for mode in ("threshold", "l2", "iterations", "seed", "unequal", "residue", "duplicate", "too_long"):
        try:
            invalid[mode] = run_invalid(PUBLIC_CASES[0], mode)
        except Exception:
            invalid[mode] = False
    if not all(invalid.values()):
        fail(f"invalid-input rejection failed: {invalid}", report)
    report["invalid_inputs"] = invalid

    try:
        report["row_permutation"] = row_permutation_gate(PUBLIC_CASES[1])
    except GateFailure as error:
        fail(str(error), report)
    except Exception as error:
        fail(f"row-permutation check failed: {type(error).__name__}: {error}", report)

    cases = PUBLIC_CASES + hidden_cases()
    details: list[dict] = []
    passed_components = 0
    total_components = 4 * len(cases)
    for packet in cases:
        validate_case(packet)
        try:
            expected = run_reference(packet)
            observed = run_candidate(packet)
            invariants = candidate_invariants(observed)
            if not invariants["raw_symmetric_zero_diagonal"] or not invariants["apc_symmetric_zero_diagonal"]:
                raise RuntimeError("score matrix symmetry/diagonal invariant failed")
            if invariants["apc_formula_max_error"] > 1e-9 or not invariants["top_contacts_consistent"]:
                raise RuntimeError("APC or top-contact self-consistency invariant failed")
            if abs(expected["effective_sequences"] - observed["effective_sequences"]) > 1e-10:
                raise RuntimeError("sequence reweighting result differs")
            components, errors = compare(expected, observed)
        except Exception as error:
            components = {key: False for key in ("raw", "apc", "top_l2", "objective")}
            errors = {"runtime": f"{type(error).__name__}: {error}"}
            invariants = {}
        passed_components += sum(components.values())
        details.append({"name": packet["name"], "components": components,
                        "errors": errors, "invariants": invariants})

    reward = passed_components / total_components
    report.update({
        "status": "passed" if passed_components == total_components else "partial",
        "public_cases": len(PUBLIC_CASES),
        "hidden_cases": len(cases) - len(PUBLIC_CASES),
        "scientific_components_passed": passed_components,
        "scientific_components_total": total_components,
        "cases": details,
    })
    write_result(report, reward)


if __name__ == "__main__":
    main()
