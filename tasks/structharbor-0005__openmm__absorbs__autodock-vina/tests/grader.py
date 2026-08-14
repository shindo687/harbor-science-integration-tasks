#!/usr/bin/env python3
"""Separate, offline differential verifier for STRUCTHARBOR-0005."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess

from cases import hidden_cases, public_cases


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-vina-source")
MODULE = Path("wrappers/python/openmm/app/vina_score.py")
LOCK = Path("/tests/source-lock.json")
TERM_NAMES = ("gauss1", "gauss2", "repulsion", "hydrophobic", "hydrogen")
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
    candidate = manifest(TESTBED)
    pristine = manifest(PRISTINE)
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
        return False, "missing regular vina_score.py"
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
    # Direct donor files are never valid additions, even if renamed.
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
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["sha256"],
        "/opt/source-archives/donor-source.tar.gz": lock["donor"]["sha256"],
        "/opt/reference-vina/vina-potential-reference":
            lock["reference_runtime"]["adapter_sha256"],
    }
    for name, expected in checks.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            return False, f"provenance mismatch: {name}"
    completed = subprocess.run(
        ["/opt/reference-vina/vina-potential-reference"], input="0 0\n",
        text=True, capture_output=True, timeout=10, check=False,
    )
    if completed.returncode or completed.stdout.strip() != "1":
        return False, "native Vina reference smoke check failed"
    return True, {"archive_and_runtime_checks": len(checks),
                  "native_reference_smoke": "pass"}


def candidate_isolation_gate():
    protected = (
        "/tests", "/opt/reference-vina", "/opt/reference-vina-source",
        "/opt/pristine-host", "/opt/reference-runner", "/opt/source-archives",
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


def run_json(command, payload, *, candidate=False, timeout=60):
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


def invalid_cases():
    base = public_cases()[0]
    result = []

    def add(name, edit):
        value = copy.deepcopy(base)
        value["name"] = name
        edit(value)
        result.append(value)

    add("invalid_types_not_list", lambda x: x["receptor"].update(types="C_H"))
    add("invalid_count_mismatch", lambda x: x["ligand"]["positions"].append([1, 2, 3]))
    add("invalid_unknown_type", lambda x: x["receptor"]["types"].__setitem__(0, "Zn"))
    add("invalid_coordinate_rank", lambda x: x["ligand"]["positions"].__setitem__(0, [1, 2]))
    add("invalid_coordinate_value", lambda x: x["receptor"]["positions"][0].__setitem__(0, "nan"))
    add("invalid_torsion_float", lambda x: x.update(num_rotatable_bonds=1.5))
    add("invalid_torsion_bool", lambda x: x.update(num_rotatable_bonds=True))
    add("invalid_torsion_negative", lambda x: x.update(num_rotatable_bonds=-1))
    add("invalid_cutoff", lambda x: x.update(cutoff=0))
    add("invalid_coincident", lambda x: x["ligand"]["positions"].__setitem__(0, [0, 0, 0]))
    return result


def finite_number(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def close_number(got, want, tolerance):
    return finite_number(got) and abs(float(got) - float(want)) <= tolerance


def compare_vectors(got, want, tolerance):
    if not isinstance(got, list) or len(got) != len(want):
        return False, math.inf
    maximum = 0.0
    for got_row, want_row in zip(got, want):
        if not isinstance(got_row, list) or len(got_row) != 3:
            return False, math.inf
        for got_value, want_value in zip(got_row, want_row):
            if not finite_number(got_value):
                return False, math.inf
            maximum = max(maximum, abs(float(got_value) - float(want_value)))
    return maximum <= tolerance, maximum


def compare_case(expected, observed):
    reasons = []
    metrics = {}
    try:
        for key in ("affinity", "raw_interaction", "torsional_penalty",
                    "torsional_divisor"):
            delta = abs(float(observed[key]) - float(expected[key]))
            metrics[f"{key}_abs"] = delta
            if not close_number(observed[key], expected[key], 5e-8):
                reasons.append(key)

        got_terms = observed["terms"]
        if not isinstance(got_terms, dict) or set(got_terms) != set(TERM_NAMES):
            reasons.append("term_schema")
        else:
            term_delta = max(abs(float(got_terms[name]) - expected["terms"][name])
                             for name in TERM_NAMES)
            metrics["term_max_abs"] = term_delta
            if (any(not finite_number(got_terms[name]) for name in TERM_NAMES)
                    or term_delta > 5e-8):
                reasons.append("terms")

        got_pairs = observed["pairs"]
        want_pairs = expected["pairs"]
        if not isinstance(got_pairs, list) or len(got_pairs) != len(want_pairs):
            reasons.append("pair_inclusion")
        else:
            pair_delta = 0.0
            for got, want in zip(got_pairs, want_pairs):
                for key in ("receptor_index", "ligand_index", "receptor_type", "ligand_type"):
                    if got.get(key) != want[key]:
                        reasons.append("pair_identity")
                if not close_number(got.get("distance"), want["distance"], 1e-10):
                    reasons.append("pair_distance")
                pair_terms = got.get("terms")
                if not isinstance(pair_terms, dict) or set(pair_terms) != set(TERM_NAMES):
                    reasons.append("pair_term_schema")
                    continue
                for name in TERM_NAMES:
                    if not finite_number(pair_terms[name]):
                        reasons.append("pair_terms")
                        continue
                    pair_delta = max(pair_delta,
                                     abs(float(pair_terms[name]) - want["terms"][name]))
                if not close_number(got.get("raw_total"), want["raw_total"], 5e-8):
                    reasons.append("pair_raw_total")
            metrics["pair_term_max_abs"] = pair_delta
            if pair_delta > 5e-8:
                reasons.append("pair_terms")

        for key in ("receptor_forces", "ligand_forces"):
            ok, delta = compare_vectors(observed[key], expected[key], 2e-6)
            metrics[f"{key}_max_abs"] = delta
            if not ok:
                reasons.append(key)

        # Independently enforce the public output invariants.
        if not reasons or all(not item.startswith("malformed") for item in reasons):
            raw = float(observed["raw_interaction"])
            divisor = float(observed["torsional_divisor"])
            term_sum = sum(float(observed["terms"][name]) for name in TERM_NAMES)
            pair_sum = sum(float(pair["raw_total"]) for pair in observed["pairs"])
            if abs(raw - term_sum) > 1e-10 or abs(raw - pair_sum) > 1e-10:
                reasons.append("raw_sum_invariant")
            if abs(float(observed["affinity"]) - raw / divisor) > 1e-10:
                reasons.append("affinity_invariant")
            if abs(float(observed["torsional_penalty"])
                   - (float(observed["affinity"]) - raw)) > 1e-10:
                reasons.append("torsion_invariant")
            force_sum = [0.0, 0.0, 0.0]
            for row in observed["receptor_forces"] + observed["ligand_forces"]:
                for axis in range(3):
                    force_sum[axis] += float(row[axis])
            if max((abs(value) for value in force_sum), default=0.0) > 1e-8:
                reasons.append("net_force_invariant")
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        reasons.append(f"malformed:{type(exc).__name__}")
    return not reasons, sorted(set(reasons)), metrics


def main():
    report = {"task": "STRUCTHARBOR-0005"}
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

    invalid = invalid_cases()
    invalid_result = run_json(candidate_command, {"cases": invalid}, candidate=True)
    invalid_passed = sum("error" in item for item in invalid_result.get("cases", []))
    report["invalid_contract"] = {"passed": invalid_passed, "total": len(invalid)}
    if invalid_passed != len(invalid):
        fail("invalid-input contract gate failed", report)

    public = public_cases()
    hidden = hidden_cases()
    all_cases = public + hidden
    expected = run_json(reference_command, {"cases": all_cases})
    observed = run_json(candidate_command, {"cases": all_cases}, candidate=True)
    if len(expected.get("cases", [])) != len(all_cases):
        fail("reference result count mismatch", report)
    if len(observed.get("cases", [])) != len(all_cases):
        fail("candidate result count mismatch", report)

    rows = []
    for case, want, got in zip(all_cases, expected["cases"], observed["cases"]):
        if "result" not in want:
            fail(f"reference failed on {case['name']}", report)
        if "result" not in got:
            rows.append({"name": case["name"], "passed": False,
                         "reasons": [f"candidate_{got.get('error', 'error')}"]})
            continue
        passed, reasons, metrics = compare_case(want["result"], got["result"])
        rows.append({"name": case["name"], "passed": passed,
                     "reasons": reasons, "metrics": metrics})

    public_rows = rows[:len(public)]
    hidden_rows = rows[len(public):]
    public_passed = sum(row["passed"] for row in public_rows)
    hidden_passed = sum(row["passed"] for row in hidden_rows)
    report.update({
        "status": "graded",
        "reference": "native AutoDock Vina 1.2.7 potential classes (root-only)",
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
