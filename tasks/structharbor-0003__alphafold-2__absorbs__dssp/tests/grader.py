#!/usr/bin/env python3
"""Separate, offline differential verifier for STRUCTHARBOR-0003."""

from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import tokenize

import numpy as np

from cases import hidden_cases, public_cases


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/reference-dssp-source")
MODULE = Path("alphafold/common/secondary_structure.py")
LOCK = Path("/tests/source-lock.json")
FORBIDDEN = re.compile(
    r"\b(mkdssp|subprocess|ctypes|cffi|socket|requests|urllib|importlib|pathlib|pickle)\b"
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


def normalized_tokens(path):
    try:
        result = []
        for token in tokenize.tokenize(io.BytesIO(path.read_bytes()).readline):
            if token.type not in {
                tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL,
                tokenize.COMMENT, tokenize.STRING,
            }:
                result.append(token.string)
        return result
    except (OSError, SyntaxError, tokenize.TokenError):
        return []


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
        return False, "missing regular secondary_structure.py"
    if module.stat().st_size > 100_000:
        return False, "candidate module exceeds 100000 bytes"
    try:
        text = module.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "candidate module is not UTF-8 text"
    if FORBIDDEN.search(text):
        return False, "candidate contains a forbidden dependency or execution primitive"
    tokens = normalized_tokens(module)
    # Catch direct Python-shaped transcriptions embedded in donor documentation.
    donor_fragments = set()
    for path in DONOR.rglob("*"):
        if path.is_file() and path.stat().st_size < 500_000:
            donor = normalized_tokens(path)
            donor_fragments.update(tuple(donor[i:i + 64])
                                   for i in range(max(0, len(donor) - 63)))
    if any(tuple(tokens[i:i + 64]) in donor_fragments
           for i in range(max(0, len(tokens) - 63))):
        return False, "candidate contains a normalized donor fragment (64 tokens)"
    return True, {
        "added": added,
        "module_sha256": sha256(module),
        "module_bytes": module.stat().st_size,
        "forbidden_dependency_scan": "pass",
        "donor_fragment_scan": "pass",
    }


def provenance_gate():
    lock = json.loads(LOCK.read_text())
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["sha256"],
        "/opt/source-archives/donor-source.tar.gz": lock["donor"]["sha256"],
        "/opt/source-archives/dssp-runtime.tar.gz": lock["reference_runtime"]["relocated_archive_sha256"],
        "/opt/source-archives/dssp.conda": lock["reference_runtime"]["conda_package_sha256"],
        "/opt/dssp/share/libcifpp/components.cif": lock["reference_runtime"]["ccd_sha256"],
    }
    for name, expected in checks.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            return False, f"provenance mismatch: {name}"
    completed = subprocess.run(
        ["/opt/dssp/bin/mkdssp", "--version"], cwd="/opt/dssp/share/libcifpp",
        text=True, capture_output=True, timeout=10, check=False,
    )
    if completed.returncode or "4.4.11" not in completed.stdout + completed.stderr:
        return False, "locked mkdssp version check failed"
    return True, {"mkdssp_version": "4.4.11", "archive_checks": len(checks)}


def candidate_isolation_gate():
    protected = (
        "/tests", "/opt/dssp", "/opt/reference-dssp-source",
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


def run_json(command, payload, *, candidate=False, timeout=180):
    if candidate:
        command = [
            "runuser", "-u", "candidate", "--", "env",
            "PYTHONPATH=/testbed", "PYTHONNOUSERSITE=1",
            "OPENBLAS_NUM_THREADS=1", "OMP_NUM_THREADS=1",
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


def compact_arrays(case):
    atom_map = {"N": 0, "CA": 1, "C": 2, "O": 4}
    aa_map = {
        "ALA": 0, "ARG": 1, "ASN": 2, "ASP": 3, "CYS": 4,
        "GLN": 5, "GLU": 6, "GLY": 7, "HIS": 8, "ILE": 9,
        "LEU": 10, "LYS": 11, "MET": 12, "PHE": 13, "PRO": 14,
        "SER": 15, "THR": 16, "TRP": 17, "TYR": 18, "VAL": 19,
    }
    residues = case["residues"]
    n = len(residues)
    positions = np.zeros((n, 37, 3), dtype=float)
    mask = np.zeros((n, 37), dtype=float)
    chain_ids = {}
    aa, numbers, chains = [], [], []
    for i, residue in enumerate(residues):
        aa.append(aa_map[residue["residue_name"]])
        numbers.append(residue["residue_index"])
        chains.append(chain_ids.setdefault(residue["chain_id"], len(chain_ids)))
        for atom, xyz in residue["atoms"].items():
            positions[i, atom_map[atom]] = xyz
            mask[i, atom_map[atom]] = 1
    return {
        "atom_positions": positions.tolist(), "atom_mask": mask.tolist(),
        "aatype": aa, "residue_index": numbers, "chain_index": chains,
    }


def invalid_cases():
    raw = compact_arrays(public_cases()[0])
    result = []

    def add(name, edit):
        value = copy.deepcopy(raw)
        edit(value)
        result.append({"name": name, "raw_arrays": value})

    add("invalid_position_rank", lambda x: x.update(atom_positions=x["atom_positions"][0]))
    add("invalid_position_width", lambda x: x["atom_positions"][0].pop())
    add("invalid_mask_shape", lambda x: x["atom_mask"].pop())
    add("invalid_missing_backbone", lambda x: x["atom_mask"][3].__setitem__(4, 0))
    add("invalid_nonfinite", lambda x: x["atom_positions"][2][1].__setitem__(0, "nan"))
    add("invalid_float_aatype", lambda x: x["aatype"].__setitem__(0, 0.5))
    add("invalid_unknown_aatype", lambda x: x["aatype"].__setitem__(0, 20))
    add("invalid_negative_chain", lambda x: x["chain_index"].__setitem__(0, -1))
    add("invalid_duplicate_id", lambda x: (
        x["chain_index"].__setitem__(1, x["chain_index"][0]),
        x["residue_index"].__setitem__(1, x["residue_index"][0]),
    ))
    result.append({"name": "invalid_empty", "raw_arrays": {
        "atom_positions": [], "atom_mask": [], "aatype": [],
        "residue_index": [], "chain_index": [],
    }})
    return result


def compare_case(expected, observed):
    reasons = []
    metrics = {}
    try:
        codes = observed["secondary_structure"]
        if codes != expected["secondary_structure"]:
            reasons.append("secondary_structure")
        n = len(expected["secondary_structure"])
        if len(codes) != n or any(code not in "HBEGITSC" for code in codes):
            reasons.append("code_contract")
        for key in ("acceptor_index", "donor_index"):
            got = np.asarray(observed[key])
            want = np.asarray(expected[key])
            if got.shape != (n, 2) or not np.array_equal(got, want):
                reasons.append(key)
        for key in ("acceptor_energy", "donor_energy"):
            got = np.asarray(observed[key], dtype=float)
            want = np.asarray(expected[key], dtype=float)
            if got.shape != (n, 2) or not np.all(np.isfinite(got)):
                reasons.append(key)
                continue
            delta = float(np.max(np.abs(got - want)))
            metrics[f"{key}_max_abs"] = delta
            # Legacy mkdssp renders one decimal; the candidate may retain 0.001.
            if delta > 0.051:
                reasons.append(key)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        reasons.append(f"malformed:{type(exc).__name__}")
    return not reasons, sorted(set(reasons)), metrics


def main():
    report = {"task": "STRUCTHARBOR-0003"}
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
    invalid_passed = sum("error" in item for item in invalid_result["cases"])
    report["invalid_contract"] = {"passed": invalid_passed, "total": len(invalid)}
    if invalid_passed != len(invalid):
        fail("invalid-input contract gate failed", report)

    public = public_cases()
    hidden = hidden_cases()
    all_cases = public + hidden
    expected = run_json(reference_command, {"cases": all_cases}, timeout=300)
    observed = run_json(candidate_command, {"cases": all_cases}, candidate=True, timeout=300)
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
        "reference": "native mkdssp 4.4.11 subprocess (root-only)",
        "candidate_identity": {"uid": 10001, "reference_paths_readable": False},
        "public": {"passed": public_passed, "total": len(public_rows),
                   "cases": public_rows},
        "hidden": {"passed": hidden_passed, "total": len(hidden_rows),
                   "cases": hidden_rows},
    })
    reward = hidden_passed / len(hidden_rows)
    write_report(report, reward)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        fail(f"verifier exception: {type(exc).__name__}: {exc}")
