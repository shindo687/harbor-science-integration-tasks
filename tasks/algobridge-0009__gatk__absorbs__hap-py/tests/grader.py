#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0009."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile

from cases import hidden_cases, make_reference, public_cases, variant


REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host")
DONOR = Path("/opt/donor-source")
MODULE = Path("src/main/java/org/broadinstitute/hellbender/tools/walkers/variantutils/HaplotypeCompareVariants.java")
LOCK = Path("/tests/source-lock.json")
HARNESS = Path("/opt/candidate-runner/HaplotypeCompareHarness.java")
FORBIDDEN = re.compile(
    r"\b(java\.(io|nio|net|lang\.reflect)|Runtime|ProcessBuilder|System|ClassLoader|"
    r"SecurityManager|Thread|native|synchronized)\b|Class\s*\.\s*forName|"
    r"getDeclared|setAccessible|exec\s*\(|loadLibrary", re.IGNORECASE,
)
IMPORT = re.compile(r"^\s*import\s+([A-Za-z0-9_.*]+)\s*;", re.MULTILINE)


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
    return any(part.startswith(".") for part in path.parts) or "__pycache__" in path.parts


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
    if not module.is_file() or module.is_symlink() or module.stat().st_size > 60_000:
        return False, "missing, linked, or oversized HaplotypeCompareVariants.java"
    try:
        text = module.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False, "candidate source is not UTF-8"
    if "package org.broadinstitute.hellbender.tools.walkers.variantutils;" not in text:
        return False, "candidate source has the wrong GATK package"
    if not re.search(r"public\s+final\s+class\s+HaplotypeCompareVariants\b", text):
        return False, "candidate source omits the required public class"
    imports = IMPORT.findall(text)
    if any(not name.startswith("java.util.") for name in imports):
        return False, f"unsupported imports: {imports}"
    if FORBIDDEN.search(text):
        return False, "candidate contains a forbidden execution or access primitive"
    donor_hashes = {sha256(path) for path in DONOR.rglob("*")
                    if path.is_file() and not path.is_symlink()
                    and path.stat().st_size <= 2_000_000}
    if sha256(module) in donor_hashes:
        return False, "candidate is a copied donor file"
    return True, {
        "added": added,
        "module_sha256": sha256(module),
        "module_bytes": module.stat().st_size,
        "allowed_import_scan": "pass",
        "forbidden_primitive_scan": "pass",
        "donor_file_hash_scan": "pass",
    }


def provenance_gate():
    lock = json.loads(LOCK.read_text())
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["archive_sha256"],
        "/opt/source-archives/donor-source.tar.gz": lock["donor"]["archive_sha256"],
        "/opt/reference-happy/bin/xcmp": lock["reference_runtime"]["xcmp_sha256"],
        "/opt/reference-happy/bin/bgzip": lock["reference_runtime"]["bgzip_sha256"],
        "/opt/reference-happy/bin/tabix": lock["reference_runtime"]["tabix_sha256"],
        "/opt/reference-happy/bin/xcmp-build-compat.patch":
            lock["reference_runtime"]["compatibility_patch_sha256"],
    }
    for host_kind in ("host", "donor"):
        for part in lock[host_kind]["parts"]:
            checks[f"/opt/source-archives/parts/{part['name']}"] = part["sha256"]
    for name, expected in checks.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            return False, f"provenance mismatch: {name}"
    commands = (
        (["/opt/reference-happy/bin/xcmp", "--version"], "v0.3.15"),
        (["/opt/reference-happy/bin/bgzip", "--version"], "1.4.1"),
        (["/opt/reference-happy/bin/tabix", "--version"], "1.4.1"),
        (["/opt/java/openjdk/bin/java", "-version"], "17.0.19"),
    )
    versions = {}
    for command, marker in commands:
        completed = subprocess.run(command, text=True, capture_output=True,
                                   timeout=20, check=False)
        output = completed.stdout + completed.stderr
        if completed.returncode or marker not in output:
            return False, f"reference runtime smoke check failed: {command[0]}"
        versions[Path(command[0]).name] = marker
    return True, {"authenticated_files": len(checks), "versions": versions}


def candidate_isolation_gate():
    protected = (
        "/tests", "/opt/reference-happy", "/opt/donor-source",
        "/opt/pristine-host", "/opt/reference-runner", "/opt/source-archives",
        "/opt/candidate-runner/HaplotypeCompareHarness.java",
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


def compile_candidate():
    classes = Path(tempfile.mkdtemp(prefix="algobridge-candidate-classes-"))
    completed = subprocess.run(
        ["/opt/java/openjdk/bin/javac", "-encoding", "UTF-8", "-d", str(classes),
         str(TESTBED / MODULE), str(HARNESS)],
        text=True, capture_output=True, timeout=60, check=False,
    )
    if completed.returncode:
        return False, completed.stderr[-1800:]
    classes.chmod(0o755)
    for path in classes.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o444)
    return True, {"classes": str(classes)}


def run_one(command, payload, *, candidate=False, classes=None, timeout=40):
    if candidate:
        command = [
            "runuser", "-u", "candidate", "--", "env",
            f"CANDIDATE_CLASSES={classes}", "PYTHONDONTWRITEBYTECODE=1",
        ] + command
    completed = subprocess.run(
        command, input=json.dumps(payload, allow_nan=False) + "\n", text=True,
        capture_output=True, timeout=timeout, check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {completed.stderr[-1800:]}"
        )
    lines = completed.stdout.strip().splitlines()
    if len(lines) != 1:
        raise RuntimeError(f"expected one JSON line, got {len(lines)}")
    try:
        return json.loads(lines[0])
    except json.JSONDecodeError as error:
        raise RuntimeError(f"invalid JSON output: {completed.stdout[-1800:]}") from error


def compare_result(expected, observed):
    reasons = []
    if not isinstance(observed, dict) or set(observed) != {"truth", "query", "summary"}:
        return False, ["result_schema"]
    for side in ("truth", "query"):
        if observed.get(side) != expected[side]:
            reasons.append(side + "_statuses")
    summary = observed.get("summary")
    if not isinstance(summary, dict) or set(summary) != {
            "truth_tp", "query_tp", "fp", "fn", "precision", "recall", "f1"}:
        reasons.append("summary_schema")
        return False, reasons
    for key in ("truth_tp", "query_tp", "fp", "fn"):
        if type(summary[key]) is not int or summary[key] != expected["summary"][key]:
            reasons.append(key)
    for key in ("precision", "recall", "f1"):
        value = summary[key]
        if (not isinstance(value, (int, float)) or isinstance(value, bool)
                or not math.isfinite(value)
                or abs(float(value) - expected["summary"][key]) > 1.0e-12):
            reasons.append(key)
    return not reasons, sorted(set(reasons))


def invalid_cases():
    base = public_cases()[0]
    result = []

    def add(name, edit):
        value = copy.deepcopy(base)
        edit(value)
        result.append((name, value))

    add("lowercase_reference", lambda x: x.update(reference=x["reference"].lower()))
    add("reference_too_short", lambda x: x.update(reference=x["reference"][:63]))
    add("reference_too_long", lambda x: x.update(reference=make_reference(0, 513)))
    add("nonpositive_reference_start", lambda x: x.update(reference_start=0))
    add("null_truth_list", lambda x: x.update(truth=None))

    def too_many(x):
        reference = make_reference(1, 512)
        variants = []
        for index, position in enumerate(range(2, 497, 15)):
            ref = reference[position - 1]
            alt = next(base for base in "ACGT" if base != ref)
            variants.append(variant(reference, f"v{index}", position, alt))
        x.update(reference=reference, truth=variants, query=[])
    add("too_many_variants", too_many)
    add("duplicate_ids", lambda x: x.update(truth=[x["truth"][0], copy.deepcopy(x["truth"][0])]))
    add("reference_allele_mismatch", lambda x: x["truth"][0].update(ref="N"))
    add("unsupported_mnp", lambda x: x["truth"][0].update(
        ref=x["reference"][26:28], alt="TT" if x["reference"][26:28] != "TT" else "AA"))
    add("indel_over_50bp", lambda x: x["truth"][0].update(
        alt=x["truth"][0]["ref"] + "A" * 51))
    add("unsupported_genotype", lambda x: x["truth"][0].update(genotype="0/0"))

    def overlap(x):
        first = variant(x["reference"], "overlap_a", 40, x["reference"][39], ref_length=2)
        ref = x["reference"][40]
        alt = next(base for base in "ACGT" if base != ref)
        second = variant(x["reference"], "overlap_b", 41, alt)
        x.update(truth=[first, second], query=[])
    add("overlapping_variants", overlap)
    return result


def swap_expected(result):
    def invert(values, unmatched):
        return [{"id": item["id"], "status": "TP" if item["status"] == "TP" else unmatched}
                for item in values]
    summary = result["summary"]
    return {
        "truth": invert(result["query"], "FN"),
        "query": invert(result["truth"], "FP"),
        "summary": {
            "truth_tp": summary["query_tp"], "query_tp": summary["truth_tp"],
            "fp": summary["fn"], "fn": summary["fp"],
            "precision": summary["recall"], "recall": summary["precision"],
            "f1": summary["f1"],
        },
    }


def main():
    report = {"task": "ALGOBRIDGE-0009", "hard_gates": {}}
    ok, detail = provenance_gate()
    report["hard_gates"]["provenance"] = detail
    if not ok:
        fail(detail, report)
    ok, detail = source_policy()
    report["hard_gates"]["source_policy"] = detail
    if not ok:
        fail(detail, report)
    ok, detail = candidate_isolation_gate()
    report["hard_gates"]["candidate_isolation"] = detail
    if not ok:
        fail(detail, report)
    ok, detail = compile_candidate()
    report["hard_gates"]["java_compile"] = detail
    if not ok:
        fail("candidate Java compilation failed", report)
    classes = detail["classes"]

    reference_command = ["python", "/opt/reference-runner/reference_runner.py"]
    candidate_command = ["python", "/opt/candidate-runner/candidate_runner.py"]
    groups = (("public", public_cases()), ("hidden", hidden_cases()))
    scientific = {}
    passed_total = 0
    total = 0
    cached = {}
    failures = []
    for group_name, cases in groups:
        passed = 0
        for packet in cases:
            total += 1
            try:
                expected_outer = run_one(reference_command, packet)
                observed_outer = run_one(candidate_command, packet, candidate=True,
                                         classes=classes)
                if not expected_outer.get("ok"):
                    raise RuntimeError("locked reference rejected a valid case: "
                                       + expected_outer.get("error", "unknown"))
                if not observed_outer.get("ok"):
                    reasons = ["candidate_exception"]
                    good = False
                else:
                    good, reasons = compare_result(expected_outer["result"],
                                                   observed_outer["result"])
                cached[packet["name"]] = (packet, expected_outer["result"], observed_outer)
                if good:
                    passed += 1
                    passed_total += 1
                else:
                    failures.append({"case": packet["name"], "reasons": reasons})
            except Exception as error:
                failures.append({"case": packet["name"],
                                 "reasons": [f"{type(error).__name__}: {error}"]})
        scientific[group_name] = {"passed": passed, "total": len(cases)}
    report["scientific"] = scientific
    report["scientific_failures"] = failures[:20]

    invalid_passed = 0
    invalid_failures = []
    for name, packet in invalid_cases():
        try:
            observed = run_one(candidate_command, packet, candidate=True, classes=classes)
            if observed.get("ok") is False:
                invalid_passed += 1
            else:
                invalid_failures.append(name)
        except Exception:
            invalid_failures.append(name)
    report["hard_gates"]["invalid_inputs"] = {
        "passed": invalid_passed, "total": 12, "failures": invalid_failures,
    }
    if invalid_passed != 12:
        fail("invalid-input rejection gate failed", report)

    metamorphic_passed = 0
    metamorphic_failures = []
    base_packet, _, base_observed_outer = cached["public_mixed_tp_fp_fn"]
    if not base_observed_outer.get("ok"):
        fail("metamorphic baseline raised an exception", report)
    base_candidate = base_observed_outer["result"]
    swapped = copy.deepcopy(base_packet)
    swapped["name"] = "metamorphic_swap_truth_query"
    swapped["truth"], swapped["query"] = swapped["query"], swapped["truth"]
    try:
        observed = run_one(candidate_command, swapped, candidate=True, classes=classes)
        good, _ = ((False, []) if not observed.get("ok") else
                   compare_result(swap_expected(base_candidate), observed["result"]))
        if good:
            metamorphic_passed += 1
        else:
            metamorphic_failures.append("swap_truth_query")
    except Exception:
        metamorphic_failures.append("swap_truth_query")

    shifted = copy.deepcopy(base_packet)
    shifted["name"] = "metamorphic_reference_prefix_shift"
    prefix = "GATTACA"
    shifted["reference"] = prefix + shifted["reference"]
    for side in ("truth", "query"):
        for item in shifted[side]:
            item["position"] += len(prefix)
    try:
        observed = run_one(candidate_command, shifted, candidate=True, classes=classes)
        good, _ = ((False, []) if not observed.get("ok") else
                   compare_result(base_candidate, observed["result"]))
        if good:
            metamorphic_passed += 1
        else:
            metamorphic_failures.append("reference_prefix_shift")
    except Exception:
        metamorphic_failures.append("reference_prefix_shift")
    report["hard_gates"]["metamorphic"] = {
        "passed": metamorphic_passed, "total": 2, "failures": metamorphic_failures,
    }
    if metamorphic_passed != 2:
        fail("metamorphic gate failed", report)

    reward = passed_total / total
    report.update({"status": "passed" if passed_total == total else "scientific_failures",
                   "scientific_passed": passed_total, "scientific_total": total})
    write_report(report, reward)


if __name__ == "__main__":
    main()
