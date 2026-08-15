#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0014."""

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
MODULE = Path("src/etkdg_init.py")
LOCK = Path("/tests/source-lock.json")
FORBIDDEN = re.compile(
    r"\b(subprocess|ctypes|cffi|socket|requests|urllib|importlib|pickle)\b"
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
    if not module.is_file() or module.is_symlink() or module.stat().st_size > 120_000:
        return False, "missing, linked, or oversized etkdg_init.py"
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
    donor_hashes = {sha256(path) for path in DONOR.rglob("*")
                    if path.is_file() and path.stat().st_size <= 2_000_000}
    if sha256(module) in donor_hashes:
        return False, "candidate is a copied donor file"
    return True, {"added": added, "module_sha256": sha256(module),
                  "module_bytes": module.stat().st_size,
                  "allowed_import_scan": "pass",
                  "forbidden_dependency_scan": "pass",
                  "donor_file_hash_scan": "pass"}


def provenance_gate():
    lock = json.loads(LOCK.read_text())
    runtime = lock["reference_runtime"]
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["sha256"],
        "/opt/source-archives/donor-source.tar.gz": lock["donor"]["sha256"],
        "/opt/reference-wheels/" + runtime["rdkit_wheel"]: runtime["rdkit_wheel_sha256"],
        "/opt/reference-wheels/" + runtime["numpy_wheel"]: runtime["numpy_wheel_sha256"],
        "/opt/reference-wheels/" + runtime["pillow_wheel"]: runtime["pillow_wheel_sha256"],
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
    protected = ("/tests", "/opt/reference-rdkit", "/opt/reference-rdkit-source",
                 "/opt/reference-wheels", "/opt/pristine-host",
                 "/opt/reference-runner", "/opt/source-archives")
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


def run_json(command, payload, *, candidate=False, timeout=300):
    if candidate:
        command = ["runuser", "-u", "candidate", "--", "env",
                   "PYTHONNOUSERSITE=1", "PYTHONDONTWRITEBYTECODE=1"] + command
    completed = subprocess.run(
        command, input=json.dumps(payload, allow_nan=False), text=True,
        capture_output=True, timeout=timeout, check=False,
    )
    if completed.returncode:
        raise RuntimeError(f"command failed ({completed.returncode}): {completed.stderr[-1800:]}")
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
    add("invalid_atoms", lambda x: x.update(atomic_numbers="carbon"))
    add("invalid_atomic_number", lambda x: x["atomic_numbers"].__setitem__(0, 0))
    add("invalid_missing_pair", lambda x: x["pair_bounds"].pop())
    add("invalid_duplicate_pair", lambda x: x["pair_bounds"].__setitem__(1, copy.deepcopy(x["pair_bounds"][0])))
    add("invalid_bound_index", lambda x: x["pair_bounds"][0].update(atoms=[0, 999]))
    add("invalid_bound_order", lambda x: x["pair_bounds"][0].update(lower=3, upper=2))
    add("invalid_prune_atoms", lambda x: x.update(prune_atoms=[0, 0]))
    add("invalid_num_confs", lambda x: x.update(num_confs=0))
    add("invalid_boolean_seed", lambda x: x.update(seed=True))
    add("invalid_prune_rms", lambda x: x.update(prune_rms=-1))
    add("invalid_attempt_limit", lambda x: x.update(max_attempts=0))
    return result


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def distance(first, second):
    return math.sqrt(sum((float(first[k]) - float(second[k])) ** 2 for k in range(3)))


def volume(coords, constraint):
    center = coords[constraint["center"]]
    vectors = [[coords[index][k] - center[k] for k in range(3)]
               for index in constraint["neighbors"]]
    a, b, c = vectors
    cross = [b[1]*c[2]-b[2]*c[1], b[2]*c[0]-b[0]*c[2], b[0]*c[1]-b[1]*c[0]]
    return sum(a[k] * cross[k] for k in range(3))


def distance_matrix(coords, indices):
    return [[distance(coords[i], coords[j]) for j in indices] for i in indices]


def matrix_drms(first, second):
    values = [(first[i][j] - second[i][j]) ** 2
              for i in range(len(first)) for j in range(i + 1, len(first))]
    return math.sqrt(sum(values) / max(1, len(values)))


def compare_case(packet, expected, observed):
    reasons, metrics = [], {}
    try:
        if not isinstance(observed, dict) or set(observed) != {
                "conformers", "failures", "rmsd_matrix", "bounds", "diagnostics"}:
            return False, ["result_schema"], metrics
        size = len(packet["atomic_numbers"])
        bounds = observed["bounds"]
        bound_delta = max(abs(float(bounds[key][i][j]) - expected[f"smoothed_{key}"][i][j])
                          for key in ("lower", "upper")
                          for i in range(size) for j in range(size))
        metrics["smoothed_bound_max_abs"] = bound_delta
        if bound_delta > 1e-9:
            reasons.append("triangle_smoothing")
        conformers = observed["conformers"]
        if not isinstance(conformers, list) or not expected["native_count"] <= len(conformers) <= packet["num_confs"]:
            reasons.append("conformer_count")
            conformers = [] if not isinstance(conformers, list) else conformers
        max_violation = 0.0
        candidate_matrices = []
        for coords in conformers:
            if (not isinstance(coords, list) or len(coords) != size
                    or any(not isinstance(row, list) or len(row) != 3
                           or any(not finite(value) for value in row) for row in coords)):
                reasons.append("coordinate_schema")
                continue
            for i in range(size):
                for j in range(i + 1, size):
                    value = distance(coords[i], coords[j])
                    max_violation = max(max_violation,
                                        expected["smoothed_lower"][i][j] - value,
                                        value - expected["smoothed_upper"][i][j])
            for constraint in packet["chiral_constraints"]:
                score = constraint["sign"] * volume(coords, constraint)
                if score < constraint["min_volume"] * 0.95:
                    reasons.append("chirality")
            candidate_matrices.append(distance_matrix(coords, packet["prune_atoms"]))
        metrics["max_bound_violation"] = max_violation
        if max_violation > 0.35:
            reasons.append("distance_bounds")
        coverage = []
        for native in expected["native_distance_matrices"]:
            coverage.append(min((matrix_drms(native, value) for value in candidate_matrices),
                                default=math.inf))
        metrics["native_coverage_max_drms"] = max(coverage, default=math.inf)
        if metrics["native_coverage_max_drms"] > 0.80:
            reasons.append("native_coverage")
        rmsd = observed["rmsd_matrix"]
        if (not isinstance(rmsd, list) or len(rmsd) != len(candidate_matrices)
                or any(not isinstance(row, list) or len(row) != len(candidate_matrices) for row in rmsd)):
            reasons.append("rmsd_schema")
        else:
            rms_delta, minimum = 0.0, math.inf
            for i in range(len(candidate_matrices)):
                for j in range(len(candidate_matrices)):
                    want = matrix_drms(candidate_matrices[i], candidate_matrices[j])
                    if not finite(rmsd[i][j]):
                        reasons.append("rmsd_nonfinite")
                    else:
                        rms_delta = max(rms_delta, abs(float(rmsd[i][j]) - want))
                    if i < j:
                        minimum = min(minimum, want)
            metrics["rmsd_matrix_max_abs"] = rms_delta
            metrics["minimum_pair_drms"] = minimum if len(candidate_matrices) > 1 else None
            if rms_delta > 1e-9:
                reasons.append("rmsd_values")
            if len(candidate_matrices) > 1 and minimum + 1e-9 < packet["prune_rms"]:
                reasons.append("rmsd_pruning")
        if (not isinstance(observed["failures"], int) or isinstance(observed["failures"], bool)
                or observed["failures"] < 0):
            reasons.append("failure_count")
        diagnostics = observed["diagnostics"]
        if (not isinstance(diagnostics, dict)
                or diagnostics.get("accepted") != len(conformers)
                or diagnostics.get("triangle_smoothed") is not True
                or diagnostics.get("deterministic_seed") != packet["seed"]
                or not isinstance(diagnostics.get("attempts"), int)
                or not 1 <= diagnostics.get("attempts", 0) <= packet["max_attempts"]):
            reasons.append("diagnostics")
    except (KeyError, TypeError, ValueError, OverflowError, ZeroDivisionError) as exc:
        reasons.append(f"malformed:{type(exc).__name__}")
    return not reasons, sorted(set(reasons)), metrics


def main():
    report = {"task": "ALGOBRIDGE-0014"}
    for name, gate in (("source_policy", source_policy),
                       ("provenance", provenance_gate),
                       ("candidate_isolation", candidate_isolation_gate)):
        ok, detail = gate()
        report[name] = detail
        if not ok:
            fail(str(detail), report)
    candidate_command = ["python", "/opt/candidate-runner/candidate_runner.py"]
    reference_command = ["python", "/opt/reference-runner/reference_runner.py"]
    descriptions = public_cases() + hidden_cases()
    reference = run_json(reference_command, {"cases": descriptions})
    expected_rows = reference.get("cases", [])
    if len(expected_rows) != len(descriptions) or any("result" not in row for row in expected_rows):
        fail("native RDKit reference failed", report)

    invalid = invalid_cases(expected_rows[0]["packet"])
    invalid_result = run_json(candidate_command, {"cases": invalid}, candidate=True)
    invalid_passed = sum("error" in item for item in invalid_result.get("cases", []))
    report["invalid_contract"] = {"passed": invalid_passed, "total": len(invalid)}
    if invalid_passed != len(invalid):
        fail("invalid-input contract gate failed", report)

    inputs = [candidate_case(row["name"], row["packet"]) for row in expected_rows]
    observed = run_json(candidate_command, {"cases": inputs}, candidate=True, timeout=600)
    if len(observed.get("cases", [])) != len(inputs):
        fail("candidate result count mismatch", report)
    rows = []
    for expected, got in zip(expected_rows, observed["cases"]):
        if "result" not in got:
            rows.append({"name": expected["name"], "passed": False,
                         "reasons": [f"candidate_{got.get('error', 'error')}"]})
        else:
            passed, reasons, metrics = compare_case(
                expected["packet"], expected["result"], got["result"])
            rows.append({"name": expected["name"], "passed": passed,
                         "reasons": reasons, "metrics": metrics})

    deterministic_case = inputs[2]
    repeated = run_json(candidate_command,
                        {"cases": [deterministic_case, deterministic_case]},
                        candidate=True, timeout=300).get("cases", [])
    deterministic_ok = (len(repeated) == 2 and "result" in repeated[0]
                         and repeated[0] == repeated[1])
    reordered_packet = copy.deepcopy(expected_rows[5]["packet"])
    reordered_packet["pair_bounds"].reverse()
    reorder_run = run_json(candidate_command, {"cases": [
        candidate_case("metamorphic_original", expected_rows[5]["packet"]),
        candidate_case("metamorphic_reordered", reordered_packet),
    ]}, candidate=True, timeout=300).get("cases", [])
    reorder_ok = (len(reorder_run) == 2 and "result" in reorder_run[0]
                  and reorder_run[0]["result"] == reorder_run[1]["result"])
    report["metamorphic"] = {
        "passed": int(deterministic_ok) + int(reorder_ok), "total": 2,
        "cases": [{"name": "fixed_seed_determinism", "passed": deterministic_ok},
                  {"name": "bound_record_reordering", "passed": reorder_ok}],
    }
    if not deterministic_ok or not reorder_ok:
        fail("metamorphic contract gate failed", report)

    public_count = len(public_cases())
    public_rows, hidden_rows = rows[:public_count], rows[public_count:]
    public_passed = sum(row["passed"] for row in public_rows)
    hidden_passed = sum(row["passed"] for row in hidden_rows)
    report.update({
        "status": "graded",
        "reference": "official RDKit 2026.03.5 ETKDGv3 (root-only)",
        "candidate_identity": {"uid": 10001, "reference_paths_readable": False},
        "public": {"passed": public_passed, "total": len(public_rows), "cases": public_rows},
        "hidden": {"passed": hidden_passed, "total": len(hidden_rows), "cases": hidden_rows},
    })
    write_report(report, hidden_passed / len(hidden_rows))


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"verifier exception: {type(exc).__name__}: {exc}")
