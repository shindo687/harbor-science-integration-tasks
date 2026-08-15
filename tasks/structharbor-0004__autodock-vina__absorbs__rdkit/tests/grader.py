#!/usr/bin/env python3
"""Separate offline differential verifier for STRUCTHARBOR-0004."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess

from cases import hidden_cases, public_cases


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-rdkit-source")
MODULE = Path("build/python/vina/mmff94.py")
LOCK = Path("/tests/source-lock.json")
COMPONENTS = (
    "bond", "angle", "stretch_bend", "out_of_plane", "torsion",
    "van_der_waals", "electrostatic", "total",
)
TERM_LISTS = (
    "bonds", "angles", "stretch_bends", "out_of_plane", "torsions",
    "nonbonded",
)
FORBIDDEN = re.compile(
    r"\b(subprocess|ctypes|cffi|socket|requests|urllib|importlib|pickle)\b"
    r"|__import__|os\s*\.\s*system|\bpopen\s*\(|\bexec\s*\(|\beval\s*\("
    r"|\bopen\s*\(",
    re.IGNORECASE,
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


def ignored(path):
    return (any(part.startswith(".") for part in path.parts)
            or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"})


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
    candidate, pristine = manifest(TESTBED), manifest(PRISTINE)
    missing = sorted(set(pristine) - set(candidate))
    changed = sorted(name for name in set(pristine) & set(candidate)
                     if pristine[name] != candidate[name])
    added = sorted(set(candidate) - set(pristine))
    if missing:
        return False, f"host files removed: {missing[:4]}"
    if changed:
        return False, f"locked host files changed: {changed[:4]}"
    if set(added) != {str(MODULE)}:
        return False, f"unexpected added files: {added[:4]}"
    module = TESTBED / MODULE
    if not module.is_file() or module.is_symlink():
        return False, "missing regular mmff94.py"
    if module.stat().st_size > 100_000:
        return False, "candidate module exceeds 100000 bytes"
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
    if imports - {"__future__", "math"}:
        return False, f"candidate imports unsupported modules: {sorted(imports)}"
    donor_hashes = {
        sha256(path) for path in DONOR.rglob("*")
        if path.is_file() and path.stat().st_size <= 2_000_000
    }
    if sha256(module) in donor_hashes:
        return False, "candidate is a copied donor file"
    return True, {
        "added": added,
        "module_sha256": sha256(module),
        "module_bytes": module.stat().st_size,
        "allowed_import_scan": "pass",
        "forbidden_dependency_scan": "pass",
        "donor_file_hash_scan": "pass",
    }


def provenance_gate():
    lock = json.loads(LOCK.read_text())
    runtime = lock["reference_runtime"]
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["sha256"],
        "/opt/source-archives/donor-source.tar.gz": lock["donor"]["sha256"],
        "/opt/reference-wheels/" + runtime["rdkit_wheel"]:
            runtime["rdkit_wheel_sha256"],
        "/opt/reference-wheels/" + runtime["numpy_wheel"]:
            runtime["numpy_wheel_sha256"],
        "/opt/reference-wheels/" + runtime["pillow_wheel"]:
            runtime["pillow_wheel_sha256"],
    }
    for name, expected in checks.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            return False, f"provenance mismatch: {name}"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = "/opt/reference-rdkit/python"
    completed = subprocess.run(
        ["python", "-c", "import rdkit; print(rdkit.__version__)"],
        text=True, capture_output=True, timeout=30, check=False, env=environment,
    )
    if completed.returncode or completed.stdout.strip() != "2026.03.5":
        return False, "locked RDKit reference smoke check failed"
    return True, {"archive_and_wheel_checks": len(checks),
                  "rdkit_version": completed.stdout.strip()}


def candidate_isolation_gate():
    protected = (
        "/tests", "/opt/reference-rdkit", "/opt/reference-rdkit-source",
        "/opt/reference-wheels", "/opt/pristine-host",
        "/opt/reference-runner", "/opt/source-archives",
    )
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


def run_json(command, payload, *, candidate=False, timeout=180):
    if candidate:
        command = [
            "runuser", "-u", "candidate", "--", "env",
            "PYTHONNOUSERSITE=1", "PYTHONDONTWRITEBYTECODE=1",
        ] + command
    completed = subprocess.run(
        command, input=json.dumps(payload, allow_nan=False), text=True,
        capture_output=True, timeout=timeout, check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stderr[-1800:]}"
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid JSON output: {completed.stdout[-1800:]}") from exc


def candidate_case(name, packet):
    return {"name": name, "packet": packet}


def invalid_cases(packet):
    result = []

    def add(name, edit):
        value = copy.deepcopy(packet)
        edit(value)
        result.append(candidate_case(name, value))

    add("invalid_schema", lambda x: x.update(schema="unknown"))
    add("invalid_empty_positions", lambda x: x.update(positions=[]))
    add("invalid_coordinate_rank", lambda x: x["positions"].__setitem__(0, [0, 1]))
    add("invalid_coordinate_value", lambda x: x["positions"][0].__setitem__(0, "nan"))
    add("invalid_missing_term_list", lambda x: x.pop("angles"))
    add("invalid_atom_index", lambda x: x["bonds"][0]["atoms"].__setitem__(0, 999))
    add("invalid_boolean_index", lambda x: x["bonds"][0]["atoms"].__setitem__(0, True))
    add("invalid_duplicate_atoms", lambda x: x["bonds"][0].update(atoms=[0, 0]))
    add("invalid_negative_bond_constant", lambda x: x["bonds"][0].update(kb=-1))
    add("invalid_dielectric_model", lambda x: x["nonbonded"][0].update(dielectric_model=3))
    add("invalid_nonbonded_flag", lambda x: x["nonbonded"][0].update(is_1_4=1))
    add("invalid_degenerate_bond", lambda x: x["positions"].__setitem__(
        x["bonds"][0]["atoms"][1], list(x["positions"][x["bonds"][0]["atoms"][0]])
    ))
    return result


def finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def compare_case(expected, observed, tolerance=1e-7):
    reasons = []
    metrics = {}
    if not isinstance(observed, dict) or set(observed) != set(COMPONENTS):
        return False, ["result_schema"], metrics
    for name in COMPONENTS:
        if not finite_number(observed[name]):
            reasons.append(f"nonfinite_{name}")
            continue
        delta = abs(float(observed[name]) - float(expected[name]))
        metrics[f"{name}_abs"] = delta
        if delta > tolerance:
            reasons.append(name)
    if all(finite_number(observed[name]) for name in COMPONENTS):
        component_sum = sum(float(observed[name]) for name in COMPONENTS[:-1])
        if abs(float(observed["total"]) - component_sum) > 1e-10:
            reasons.append("total_sum_invariant")
    return not reasons, sorted(set(reasons)), metrics


def rigid_transform(packet):
    result = copy.deepcopy(packet)
    result["positions"] = [
        [xyz[2] + 17.0, xyz[0] - 23.0, xyz[1] + 9.0]
        for xyz in result["positions"]
    ]
    return result


def reordered(packet):
    result = copy.deepcopy(packet)
    for name in TERM_LISTS:
        result[name] = list(reversed(result[name]))
    return result


def main():
    report = {"task": "STRUCTHARBOR-0004"}
    policy_ok, policy = source_policy()
    report["source_policy"] = policy
    if not policy_ok:
        fail(str(policy), report)
    provenance_ok, provenance = provenance_gate()
    report["provenance"] = provenance
    if not provenance_ok:
        fail(str(provenance), report)
    isolation_ok, isolation = candidate_isolation_gate()
    report["candidate_isolation"] = isolation
    if not isolation_ok:
        fail(str(isolation), report)

    candidate_command = ["python", "/opt/candidate-runner/candidate_runner.py"]
    reference_command = ["python", "/opt/reference-runner/reference_runner.py"]
    public, hidden = public_cases(), hidden_cases()
    descriptions = public + hidden
    reference = run_json(reference_command, {"cases": descriptions})
    expected_rows = reference.get("cases", [])
    if len(expected_rows) != len(descriptions):
        fail("reference result count mismatch", report)
    for description, row in zip(descriptions, expected_rows):
        if "packet" not in row or "result" not in row:
            fail(f"reference failed on {description['name']}", report)

    invalid = invalid_cases(expected_rows[0]["packet"])
    invalid_result = run_json(candidate_command, {"cases": invalid}, candidate=True)
    invalid_passed = sum("error" in item for item in invalid_result.get("cases", []))
    report["invalid_contract"] = {"passed": invalid_passed, "total": len(invalid)}
    if invalid_passed != len(invalid):
        fail("invalid-input contract gate failed", report)

    candidate_inputs = [candidate_case(row["name"], row["packet"])
                        for row in expected_rows]
    observed = run_json(candidate_command, {"cases": candidate_inputs}, candidate=True)
    if len(observed.get("cases", [])) != len(descriptions):
        fail("candidate result count mismatch", report)

    rows = []
    for expected, got in zip(expected_rows, observed["cases"]):
        if "result" not in got:
            rows.append({"name": expected["name"], "passed": False,
                         "reasons": [f"candidate_{got.get('error', 'error')}"]})
            continue
        passed, reasons, metrics = compare_case(expected["result"], got["result"])
        rows.append({"name": expected["name"], "passed": passed,
                     "reasons": reasons, "metrics": metrics})

    metamorphic_inputs = [
        candidate_case("metamorphic_rigid_transform",
                       rigid_transform(expected_rows[7]["packet"])),
        candidate_case("metamorphic_record_reordering",
                       reordered(expected_rows[11]["packet"])),
    ]
    # Metamorphic gates check self-consistency independently of differential
    # correctness, so scientifically plausible near misses can still receive a
    # partial hidden-case reward instead of being collapsed to a hard-gate zero.
    metamorphic_expected = [observed["cases"][7]["result"],
                            observed["cases"][11]["result"]]
    metamorphic_observed = run_json(
        candidate_command, {"cases": metamorphic_inputs}, candidate=True,
    ).get("cases", [])
    metamorphic_rows = []
    if len(metamorphic_observed) != 2:
        fail("metamorphic result count mismatch", report)
    for item, expected in zip(metamorphic_observed, metamorphic_expected):
        if "result" not in item:
            metamorphic_rows.append({"name": item.get("name"), "passed": False,
                                     "reasons": [item.get("error", "error")]})
        else:
            passed, reasons, metrics = compare_case(expected, item["result"])
            metamorphic_rows.append({"name": item["name"], "passed": passed,
                                     "reasons": reasons, "metrics": metrics})
    report["metamorphic"] = {
        "passed": sum(row["passed"] for row in metamorphic_rows),
        "total": len(metamorphic_rows), "cases": metamorphic_rows,
    }
    if not all(row["passed"] for row in metamorphic_rows):
        fail("metamorphic contract gate failed", report)

    public_rows, hidden_rows = rows[:len(public)], rows[len(public):]
    public_passed = sum(row["passed"] for row in public_rows)
    hidden_passed = sum(row["passed"] for row in hidden_rows)
    report.update({
        "status": "graded",
        "reference": "official RDKit 2026.03.5 MMFF94 force fields (root-only)",
        "candidate_identity": {"uid": 10001, "reference_paths_readable": False},
        "public": {"passed": public_passed, "total": len(public_rows),
                   "cases": public_rows},
        "hidden": {"passed": hidden_passed, "total": len(hidden_rows),
                   "cases": hidden_rows},
    })
    write_report(report, hidden_passed / len(hidden_rows))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"verifier exception: {type(exc).__name__}: {exc}")
