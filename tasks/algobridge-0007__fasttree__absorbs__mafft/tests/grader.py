#!/usr/bin/env python3
"""Isolated differential grader for FastTree native progressive alignment."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import pwd
import resource
import shutil
import subprocess
import tempfile
import traceback

from cases import CASES, DEFAULT_GAP_EXTEND, DEFAULT_GAP_OPEN, LEGACY_ALIGNMENT
from common import (
    affine_sp_score,
    alignment_homology,
    alignment_invariants,
    format_fasta,
    homology_f1,
    leaf_names,
    normalized_splits,
    parse_fasta,
    parse_newick,
    tree_invariants,
    trees_equivalent,
)
from reference_runner import run_legacy, run_reference
from guide_oracle import bounded_upgma
from source_policy import check_source_policy


TESTBED = Path("/testbed")
LOGS = Path("/logs/verifier")
REPORT = LOGS / "report.json"
REWARD = LOGS / "reward.txt"
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001


def _sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _drop_privileges():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (16 * 1024 * 1024, 16 * 1024 * 1024))
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def _run(command, *, cwd, env, timeout=30, candidate=False):
    return subprocess.run(
        [str(value) for value in command],
        cwd=str(cwd),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        preexec_fn=_drop_privileges if candidate else None,
    )


def _remove_reference_assets():
    targets = [
        Path("/opt/reference-tools"),
        Path("/opt/reference-mafft-source"),
        Path("/opt/pristine-host"),
        Path("/opt/task-inputs"),
    ]
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
    leftovers = [str(path) for path in targets if path.exists()]
    if leftovers:
        raise RuntimeError(f"reference cleanup failed: {leftovers}")
    if shutil.which("mafft") is not None:
        raise RuntimeError("mafft remains discoverable in candidate PATH")
    return {
        "removed": [str(path) for path in targets],
        "mafft_in_path": False,
    }


def _prepare_candidate():
    stage = Path(tempfile.mkdtemp(prefix="candidate-build-"))
    stage.chmod(0o755)
    for path in sorted(TESTBED.iterdir()):
        if path.is_file() and (path.suffix in {".c", ".h"} or path.name == "wag.mat"):
            shutil.copy2(path, stage / path.name)
    source_files = sorted(stage.glob("*.c"))
    if not source_files:
        raise RuntimeError("candidate has no root-level C source files")
    binary = stage / "FastTree-candidate"
    command = [
        "/usr/bin/gcc",
        "-O3",
        "-std=c99",
        "-I",
        stage,
        "-o",
        binary,
        *source_files,
        "-lm",
    ]
    completed = _run(command, cwd=stage, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C.UTF-8"}, timeout=120)
    if completed.returncode != 0:
        raise RuntimeError(f"candidate compilation failed:\n{completed.stderr[-8000:]}")
    binary.chmod(0o555)
    return stage, binary, {
        "command": [str(value) for value in command],
        "source_files": [path.name for path in source_files],
        "stderr_tail": completed.stderr[-4000:],
        "binary_sha256": _sha256(binary),
    }


def _candidate_environment(root):
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(root),
        "TMPDIR": str(root),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "OMP_NUM_THREADS": "1",
    }


def _run_candidate_case(binary, case):
    root = Path(tempfile.mkdtemp(prefix=f"candidate-{case['id']}-"))
    root.chmod(0o755)
    os.chown(root, CANDIDATE_UID, CANDIDATE_GID)
    input_path = root / "input.fa"
    alignment_path = root / "alignment.fa"
    guide_path = root / "guide.nwk"
    input_path.write_text(format_fasta(case["records"]))
    input_path.chmod(0o444)
    command = [binary]
    if case["alphabet"] == "dna":
        command.append("-nt")
    command.extend(
        [
            "-quiet",
            "-noboot",
            "--align-small",
            "--alignment-out",
            alignment_path,
            "--guide-tree-out",
            guide_path,
            "--align-matrix",
            "identity" if case["alphabet"] == "dna" else "blosum62",
            "--align-gap-open",
            str(DEFAULT_GAP_OPEN),
            "--align-gap-extend",
            str(DEFAULT_GAP_EXTEND),
            input_path,
        ]
    )
    completed = _run(
        command,
        cwd=root,
        env=_candidate_environment(root),
        timeout=30,
        candidate=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"candidate exited {completed.returncode}; stderr:\n{completed.stderr[-4000:]}"
        )
    if not alignment_path.is_file() or not guide_path.is_file():
        raise RuntimeError("candidate did not create both requested output files")
    if alignment_path.stat().st_size > 2_000_000 or guide_path.stat().st_size > 2_000_000:
        raise RuntimeError("candidate output exceeds size limit")
    alignment_text = alignment_path.read_text()
    guide_text = guide_path.read_text().strip()
    final_text = completed.stdout.strip()
    return {
        "alignment_text": alignment_text,
        "alignment": parse_fasta(alignment_text),
        "guide_text": guide_text,
        "guide": parse_newick(guide_text),
        "final_tree_text": final_text,
        "final_tree": parse_newick(final_text),
        "stderr_tail": completed.stderr[-2000:],
    }


def _run_candidate_legacy(binary):
    root = Path(tempfile.mkdtemp(prefix="candidate-legacy-"))
    root.chmod(0o755)
    os.chown(root, CANDIDATE_UID, CANDIDATE_GID)
    input_path = root / "aligned.fa"
    input_path.write_text(format_fasta(LEGACY_ALIGNMENT))
    input_path.chmod(0o444)
    completed = _run(
        [binary, "-nt", "-quiet", "-noboot", input_path],
        cwd=root,
        env=_candidate_environment(root),
        timeout=30,
        candidate=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"legacy FastTree invocation failed: {completed.stderr[-4000:]}")
    return parse_newick(completed.stdout.strip())


def _evaluate_case(case, reference, expected_guide, candidate):
    problems = alignment_invariants(case["records"], candidate["alignment"], case["alphabet"])
    names = [name for name, _ in case["records"]]
    problems.extend(f"guide: {item}" for item in tree_invariants(candidate["guide"], names, True))
    problems.extend(f"final: {item}" for item in tree_invariants(candidate["final_tree"], names, False))

    ref_homology = alignment_homology(reference["alignment"])
    got_homology = alignment_homology(candidate["alignment"])
    f1 = homology_f1(ref_homology, got_homology)
    if f1 < 1.0 - 1e-12:
        problems.append(f"alignment homology F1 is {f1:.9f}, expected 1")

    reference_sp = affine_sp_score(
        reference["alignment"], case["alphabet"], DEFAULT_GAP_OPEN, DEFAULT_GAP_EXTEND
    )
    candidate_sp = affine_sp_score(
        candidate["alignment"], case["alphabet"], DEFAULT_GAP_OPEN, DEFAULT_GAP_EXTEND
    )
    sp_error = abs(reference_sp - candidate_sp)
    if sp_error > 1e-9:
        problems.append(f"affine sum-of-pairs score error is {sp_error:.9g}")

    guide_ok, guide_detail = trees_equivalent(expected_guide, candidate["guide"], 1e-5)
    if not guide_ok:
        problems.append(f"bounded UPGMA guide tree: {guide_detail}")
    mafft_guide_topology_match = (
        normalized_splits(reference["guide"]) == normalized_splits(candidate["guide"])
    )

    final_ok, final_detail = trees_equivalent(reference["final_tree"], candidate["final_tree"], 1e-5)
    if not final_ok:
        problems.append(f"final tree: {final_detail}")
    return {
        "id": case["id"],
        "passed": not problems,
        "alignment_homology_f1": f1,
        "reference_homology_pairs": len(ref_homology),
        "candidate_homology_pairs": len(got_homology),
        "reference_affine_sp_score": reference_sp,
        "candidate_affine_sp_score": candidate_sp,
        "affine_sp_score_error": sp_error,
        "bounded_upgma_guide_match": guide_ok,
        "mafft_internal_guide_topology_match_diagnostic": mafft_guide_topology_match,
        "final_tree_match": final_ok,
        "problems": problems,
        "candidate_stderr_tail": candidate["stderr_tail"],
    }


def grade():
    LOGS.mkdir(parents=True, exist_ok=True)
    gates = {}
    report = {
        "schema_version": 1,
        "task": "algobridge-0007__fasttree__absorbs__mafft",
        "hidden_case_count": len(CASES),
        "gates": gates,
        "cases": [],
    }

    source_problems, source_details = check_source_policy(
        TESTBED, "/opt/pristine-host", "/opt/reference-mafft-source"
    )
    gates["source_policy"] = {
        "passed": not source_problems,
        "problems": source_problems,
        "details": source_details,
    }
    if source_problems:
        report["reward"] = 0.0
        report["summary"] = "source policy hard gate failed"
        return report

    references = {}
    expected_guides = {}
    for case in CASES:
        reference = run_reference(case)
        inv = alignment_invariants(case["records"], reference["alignment"], case["alphabet"])
        inv += tree_invariants(reference["guide"], [name for name, _ in case["records"]], True)
        inv += tree_invariants(reference["final_tree"], [name for name, _ in case["records"]], False)
        if inv:
            raise RuntimeError(f"invalid locked reference for {case['id']}: {inv}")
        references[case["id"]] = reference
        expected_guides[case["id"]] = bounded_upgma(
            case["records"], case["alphabet"], DEFAULT_GAP_OPEN, DEFAULT_GAP_EXTEND
        )
    repeat = run_reference(CASES[0])
    ref0 = references[CASES[0]["id"]]
    deterministic = (
        alignment_homology(ref0["alignment"]) == alignment_homology(repeat["alignment"])
        and normalized_splits(ref0["guide"]) == normalized_splits(repeat["guide"])
        and trees_equivalent(ref0["final_tree"], repeat["final_tree"], 0.0)[0]
    )
    gates["reference_determinism"] = {"passed": deterministic, "case": CASES[0]["id"]}
    if not deterministic:
        raise RuntimeError("locked reference workflow is not deterministic")
    legacy_text, legacy_reference = run_legacy(LEGACY_ALIGNMENT)
    gates["reference_pipeline"] = {
        "passed": True,
        "workflow": "locked MAFFT core -> locked FastTree 2.2.0",
        "cases": len(references),
        "legacy_tree_sha256": hashlib.sha256(legacy_text.encode()).hexdigest(),
    }

    gates["candidate_isolation"] = {"passed": True, **_remove_reference_assets()}
    stage, binary, build = _prepare_candidate()
    gates["candidate_build"] = {"passed": True, **build}

    candidate_legacy = _run_candidate_legacy(binary)
    legacy_ok, legacy_detail = trees_equivalent(legacy_reference, candidate_legacy, 1e-5)
    gates["legacy_fasttree_regression"] = {"passed": legacy_ok, "detail": legacy_detail}
    if not legacy_ok:
        report["reward"] = 0.0
        report["summary"] = "legacy FastTree regression hard gate failed"
        return report

    candidates = {}
    for case in CASES:
        try:
            candidate = _run_candidate_case(binary, case)
            candidates[case["id"]] = candidate
            case_report = _evaluate_case(
                case, references[case["id"]], expected_guides[case["id"]], candidate
            )
        except Exception as exc:
            case_report = {
                "id": case["id"],
                "passed": False,
                "problems": [str(exc)],
            }
        report["cases"].append(case_report)

    groups = {}
    for case in CASES:
        group = case.get("permutation_group")
        if group and case["id"] in candidates:
            groups.setdefault(group, []).append(case["id"])
    permutation_report = {}
    for group, ids in groups.items():
        ok = len(ids) == 2
        detail = "ok"
        if ok:
            first, second = (candidates[item] for item in ids)
            ok = alignment_homology(first["alignment"]) == alignment_homology(second["alignment"])
            ok = ok and normalized_splits(first["final_tree"]) == normalized_splits(second["final_tree"])
            if not ok:
                detail = "candidate homology or final splits changed under input permutation"
        else:
            detail = "one permutation case did not produce parseable outputs"
        permutation_report[group] = {"passed": ok, "cases": ids, "detail": detail}
        if not ok:
            for case_report in report["cases"]:
                if case_report["id"] in ids:
                    case_report["passed"] = False
                    case_report.setdefault("problems", []).append(detail)
    gates["permutation_invariance"] = {
        "passed": all(item["passed"] for item in permutation_report.values()),
        "groups": permutation_report,
    }

    passed = sum(bool(item.get("passed")) for item in report["cases"])
    reward = passed / len(CASES)
    report["passed_cases"] = passed
    report["reward"] = reward
    report["summary"] = f"{passed}/{len(CASES)} hidden differential cases passed"
    return report


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        report = grade()
    except Exception as exc:
        report = {
            "schema_version": 1,
            "task": "algobridge-0007__fasttree__absorbs__mafft",
            "reward": 0.0,
            "summary": "verifier exception",
            "exception": str(exc),
            "traceback": traceback.format_exc(),
        }
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    REWARD.write_text(f"{float(report['reward']):.12g}\n")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
