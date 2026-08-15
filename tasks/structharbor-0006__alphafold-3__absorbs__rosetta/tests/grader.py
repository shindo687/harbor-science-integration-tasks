#!/usr/bin/env python3
"""Offline, separate differential verifier for STRUCTHARBOR-0006."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from cases import (finite, hidden_cases, public_cases, rotated_translated,
                   separation_scan, swapped_groups)


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
MODULE = Path("src/alphafold3/model/interface_energy_lite.py")
LOCK = Path("/tests/source-lock.json")
CALIBRATION = Path("/tests/rosetta-calibration.json")
TERM_NAMES = {"lj_repulsive", "lj_attractive", "coulomb", "hbond", "sasa"}
FORBIDDEN = re.compile(
    r"\b(subprocess|ctypes|cffi|socket|requests|urllib|importlib|pickle|pathlib)\b"
    r"|__import__|os\s*\.\s*system|\bpopen\s*\(|\bexec\s*\(|\beval\s*\("
    r"|\bopen\s*\(", re.IGNORECASE,
)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(report, reward):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["reward"] = float(reward)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    REWARD.write_text(f"{float(reward):.10f}\n")


def fail(reason, report=None):
    report = {} if report is None else report
    report.update({"status": "hard_gate_failed", "reason": reason})
    write_report(report, 0.0)
    raise SystemExit(0)


def ignored(relative):
    return (any(part.startswith(".") for part in relative.parts)
            or "__pycache__" in relative.parts
            or relative.suffix in {".pyc", ".pyo"})


def manifest(root):
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if ignored(relative):
            continue
        if path.is_symlink():
            result[str(relative)] = "SYMLINK"
        elif path.is_file():
            result[str(relative)] = sha256(path)
    return result


def source_policy():
    candidate = manifest(TESTBED)
    pristine = manifest(PRISTINE)
    missing = sorted(set(pristine) - set(candidate))
    changed = sorted(name for name in set(pristine) & set(candidate)
                     if pristine[name] != candidate[name])
    added = sorted(set(candidate) - set(pristine))
    if missing:
        return False, f"locked AlphaFold 3 files removed: {missing[:4]}"
    if changed:
        return False, f"locked AlphaFold 3 files changed: {changed[:4]}"
    if set(added) != {str(MODULE)}:
        return False, f"unexpected added files: {added[:6]}"
    module = TESTBED / MODULE
    if not module.is_file() or module.is_symlink() or module.stat().st_size > 60_000:
        return False, "candidate module is missing, linked, or too large"
    try:
        text = module.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (UnicodeDecodeError, SyntaxError):
        return False, "candidate module is not valid UTF-8 Python"
    if FORBIDDEN.search(text):
        return False, "candidate contains a forbidden dependency or execution primitive"
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    unsupported = imports - {"__future__", "math"}
    if unsupported:
        return False, f"candidate imports unsupported modules: {sorted(unsupported)}"
    return True, {
        "added": added,
        "module_sha256": sha256(module),
        "module_bytes": module.stat().st_size,
        "ast_and_dependency_scan": "pass",
        "locked_host_unchanged": True,
    }


def provenance_gate():
    lock = json.loads(LOCK.read_text())
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["archive_sha256"],
        "/tests/rosetta-calibration.json": lock["calibration"]["sha256"],
    }
    for name, expected in checks.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            return False, f"provenance mismatch: {name}"
    calibration = json.loads(CALIBRATION.read_text())
    runtime = calibration.get("rosetta_runtime", {})
    if runtime.get("binary_sha256") != lock["calibration"]["rosetta_binary_sha256"]:
        return False, "frozen Rosetta runtime hash mismatch"
    forbidden_runtime = [
        path for path in (Path("/opt/rosetta"), Path("/opt/donor-source"),
                          Path("/usr/local/bin/InterfaceAnalyzer")) if path.exists()
    ]
    if forbidden_runtime:
        return False, "Rosetta runtime or donor source was bundled into the verifier"
    return True, {
        "checked_artifacts": sorted(checks),
        "calibration_cases": len(calibration["cases"]),
        "donor_runtime_absent": True,
    }


def isolation_gate():
    protected = ("/tests", "/opt/pristine-host", "/opt/source-archives")
    readable = []
    for path in protected:
        completed = subprocess.run(
            ["runuser", "-u", "candidate", "--", "test", "-r", path],
            timeout=10, check=False,
        )
        if completed.returncode == 0:
            readable.append(path)
    if readable:
        return False, f"candidate can read protected paths: {readable}"
    return True, {"uid": 10001, "protected_paths_unreadable": list(protected)}


def run_json(command, payload, *, candidate=False, timeout=90, expect_success=True):
    if candidate:
        command = [
            "runuser", "-u", "candidate", "--", "env",
            "PYTHONNOUSERSITE=1", "PYTHONDONTWRITEBYTECODE=1",
        ] + command
    completed = subprocess.run(
        command, input=json.dumps(payload, allow_nan=False), text=True,
        capture_output=True, timeout=timeout, check=False,
    )
    if not expect_success:
        return completed.returncode, completed.stdout, completed.stderr
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stderr[-1800:]}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON output: {completed.stdout[-1800:]}") from exc


def candidate(packet, timeout=90):
    return run_json(["python3", "/opt/candidate-runner/candidate_runner.py"],
                    packet, candidate=True, timeout=timeout)


def reference(packet):
    return run_json(["python3", "/opt/reference-runner/reference_runner.py"],
                    packet, timeout=90)


def close(got, want, tolerance=2.0e-7):
    return finite(got) and finite(want) and abs(float(got) - float(want)) <= tolerance


def compare_result(got, want, *, force_tolerance=4.0e-4):
    reasons = []
    maximum = 0.0
    if not isinstance(got, dict) or set(got) != {
            "bound", "unbound", "delta", "per_residue", "forces"}:
        return False, ["top_level_schema"], math.inf
    for section in ("bound", "unbound", "delta"):
        value = got.get(section)
        if not isinstance(value, dict) or set(value) != {"terms", "total"}:
            reasons.append(f"{section}_schema")
            continue
        if not isinstance(value["terms"], dict) or set(value["terms"]) != TERM_NAMES:
            reasons.append(f"{section}_terms_schema")
            continue
        for term in TERM_NAMES:
            if finite(value["terms"].get(term)):
                maximum = max(maximum, abs(value["terms"][term] - want[section]["terms"][term]))
            if not close(value["terms"].get(term), want[section]["terms"][term]):
                reasons.append(f"{section}.{term}")
        if not close(value.get("total"), want[section]["total"]):
            reasons.append(f"{section}.total")
    residues = got.get("per_residue")
    expected_residues = want["per_residue"]
    if not isinstance(residues, list) or len(residues) != len(expected_residues):
        reasons.append("per_residue_schema")
    else:
        for observed, expected in zip(residues, expected_residues):
            if (not isinstance(observed, dict)
                    or set(observed) != {"residue", "terms", "total"}
                    or observed.get("residue") != expected["residue"]
                    or not isinstance(observed.get("terms"), dict)
                    or set(observed["terms"]) != TERM_NAMES):
                reasons.append("per_residue_schema")
                break
            for term in TERM_NAMES:
                if not close(observed["terms"].get(term), expected["terms"][term]):
                    reasons.append(f"per_residue.{expected['residue']}.{term}")
            if not close(observed.get("total"), expected["total"]):
                reasons.append(f"per_residue.{expected['residue']}.total")
    if want["forces"] is None:
        if got.get("forces") is not None:
            reasons.append("forces_should_be_null")
    else:
        forces = got.get("forces")
        if not isinstance(forces, list) or len(forces) != len(want["forces"]):
            reasons.append("forces_schema")
        else:
            for row, expected_row in zip(forces, want["forces"]):
                if not isinstance(row, list) or len(row) != 3:
                    reasons.append("forces_schema")
                    break
                for value, expected in zip(row, expected_row):
                    if not close(value, expected, force_tolerance):
                        reasons.append("forces_numeric")
    return not reasons, sorted(set(reasons)), maximum


def invalid_packets():
    base = public_cases()[0]
    cases = []

    def add(name, edit):
        value = copy.deepcopy(base)
        value["name"] = name
        edit(value)
        cases.append(value)

    add("bad_missing_field", lambda value: value.pop("group_a"))
    add("bad_extra_field", lambda value: value.update(extra=True))
    add("bad_duplicate_id", lambda value: value["atoms"][1].update(id=value["atoms"][0]["id"]))
    add("bad_nan", lambda value: value["atoms"][0]["coord"].__setitem__(0, "nan"))
    add("bad_coincident", lambda value: value["atoms"][1].update(coord=value["atoms"][0]["coord"]))
    add("bad_group_overlap", lambda value: value.update(group_b=["A", "B"]))
    add("bad_group_missing", lambda value: value.update(group_b=["C"]))
    add("bad_direction", lambda value: value.update(separation_direction=[0, 0, 0]))
    add("bad_switch", lambda value: value["parameters"].update(switch_distance=12.0))
    add("bad_force_bool", lambda value: value.update(compute_forces=1))
    add("bad_direction_shape", lambda value: value.update(separation_direction=[1, 0]))
    add("bad_atom_field", lambda value: value["atoms"][0].update(mass=12.0))
    return cases


def energy_signature(result):
    return [result[section]["terms"][term]
            for section in ("bound", "unbound", "delta")
            for term in sorted(TERM_NAMES)] + [result["delta"]["total"]]


def finite_difference_check(packet, observed):
    step = 1.0e-4
    maximum = 0.0
    for atom_index in range(len(packet["atoms"])):
        for axis in range(3):
            plus = copy.deepcopy(packet)
            minus = copy.deepcopy(packet)
            plus["compute_forces"] = False
            minus["compute_forces"] = False
            plus["atoms"][atom_index]["coord"][axis] += step
            minus["atoms"][atom_index]["coord"][axis] -= step
            numerical = -(candidate(plus)["delta"]["total"]
                          - candidate(minus)["delta"]["total"]) / (2.0 * step)
            maximum = max(maximum, abs(numerical - observed["forces"][atom_index][axis]))
    return maximum <= 2.0e-3, maximum


def ranks(values):
    result = [0.0] * len(values)
    ordered = sorted(range(len(values)), key=lambda index: values[index])
    position = 0
    while position < len(ordered):
        end = position + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[position]]:
            end += 1
        rank = 0.5 * (position + end - 1) + 1.0
        for offset in range(position, end):
            result[ordered[offset]] = rank
        position = end
    return result


def spearman(left, right):
    left_rank = ranks(left)
    right_rank = ranks(right)
    left_mean = sum(left_rank) / len(left_rank)
    right_mean = sum(right_rank) / len(right_rank)
    numerator = sum((a - left_mean) * (b - right_mean)
                    for a, b in zip(left_rank, right_rank))
    left_norm = math.sqrt(sum((a - left_mean) ** 2 for a in left_rank))
    right_norm = math.sqrt(sum((b - right_mean) ** 2 for b in right_rank))
    return numerator / (left_norm * right_norm)


def main():
    report = {"task": "structharbor-0006__alphafold-3__absorbs__rosetta"}
    ok, detail = source_policy()
    if not ok:
        fail(detail, report)
    report["source_policy"] = detail
    ok, detail = provenance_gate()
    if not ok:
        fail(detail, report)
    report["provenance"] = detail
    ok, detail = isolation_gate()
    if not ok:
        fail(detail, report)
    report["isolation"] = detail

    invalid_accepted = []
    for item in invalid_packets():
        code, _, _ = run_json(
            ["python3", "/opt/candidate-runner/candidate_runner.py"], item,
            candidate=True, timeout=30, expect_success=False,
        )
        if code == 0:
            invalid_accepted.append(item["name"])
    if invalid_accepted:
        fail(f"invalid packets accepted: {invalid_accepted}", report)
    report["invalid_input_gate"] = {"rejected": len(invalid_packets())}

    score = 8.0
    total = 80.0
    case_results = []
    exact_passed = 0
    force_passed = 0
    cases = public_cases() + hidden_cases()
    for item in cases:
        try:
            expected = reference(item)
            observed = candidate(item)
            passed, reasons, maximum = compare_result(observed, expected)
        except Exception as exc:
            passed, reasons, maximum = False, [str(exc)[-600:]], math.inf
        if passed:
            exact_passed += 1
            score += 40.0 / len(cases)
            if item["compute_forces"]:
                force_passed += 1
        case_results.append({
            "name": item["name"], "passed": passed,
            "reasons": reasons, "term_max_abs": maximum,
        })
    force_count = sum(item["compute_forces"] for item in cases)
    score += 6.0 * force_passed / force_count
    report["differential"] = {
        "passed": exact_passed, "total": len(cases), "cases": case_results,
        "force_cases_passed": force_passed, "force_cases_total": force_count,
    }

    hbond = public_cases()[2]
    hbond_observed = candidate(hbond)
    fd_ok, fd_max = finite_difference_check(hbond, hbond_observed)
    if fd_ok:
        score += 4.0
    report["finite_difference_1e-4"] = {"passed": fd_ok, "max_abs": fd_max}

    base = public_cases()[-1]
    base["compute_forces"] = False
    base_result = candidate(base)
    transformed = candidate(rotated_translated(base))
    swapped = candidate(swapped_groups(base))
    rigid_max = max(abs(a - b) for a, b in zip(
        energy_signature(base_result), energy_signature(transformed)))
    swap_max = max(abs(a - b) for a, b in zip(
        energy_signature(base_result), energy_signature(swapped)))
    scan_results = [candidate(item) for item in separation_scan(base)]
    convergence = abs(scan_results[-1]["delta"]["total"]
                      - scan_results[-2]["delta"]["total"])
    invariant_checks = {
        "common_rigid_transform": rigid_max <= 2.0e-7,
        "chain_group_swap": swap_max <= 2.0e-7,
        "infinite_separation_limit": convergence <= 2.0e-7,
    }
    score += 10.0 * sum(invariant_checks.values()) / len(invariant_checks)
    report["invariants"] = {
        "checks": invariant_checks, "rigid_max_abs": rigid_max,
        "swap_max_abs": swap_max, "far_separation_abs": convergence,
    }

    calibration = json.loads(CALIBRATION.read_text())
    rosetta_values = []
    lite_values = []
    calibration_rows = []
    for item in calibration["cases"]:
        rosetta_value = item["rosetta"]["dG_separated"]
        lite_value = candidate(item["packet"], timeout=120)["delta"]["total"]
        rosetta_values.append(rosetta_value)
        lite_values.append(lite_value)
        calibration_rows.append({
            "name": item["packet"]["name"],
            "rosetta_dG_separated": rosetta_value,
            "lite_delta": lite_value,
        })
    correlation = spearman(rosetta_values, lite_values)
    ranking_passed = correlation >= 0.98
    if ranking_passed:
        score += 12.0
    report["rosetta_ranking"] = {
        "passed": ranking_passed, "spearman": correlation,
        "threshold": 0.98, "rows": calibration_rows,
        "scope": "frozen ranking calibration only; no numerical equivalence claim",
    }

    reward = max(0.0, min(1.0, score / total))
    report.update({
        "status": "passed" if reward == 1.0 else "partial",
        "points": score, "points_total": total,
    })
    write_report(report, reward)


if __name__ == "__main__":
    main()
