#!/usr/bin/env python3
"""Isolated differential grader for native BWA biallelic SNV calling."""

from __future__ import annotations

from pathlib import Path
import hashlib
import json
import os
import resource
import shutil
import subprocess
import tempfile
import traceback
from typing import Any

from direct_matrix import compare_calls
from fixture_factory import make_fixture
from reference_runner import reference_calls
from source_policy import check_source_policy
from task_io import parse_calls, rewrite_sam_flags


TESTBED = Path("/testbed")
TESTS = Path("/tests")
LOGS = Path("/logs/verifier")
REPORT = LOGS / "report.json"
REWARD = LOGS / "reward.txt"
PRISTINE_BWA = Path("/opt/pristine-bwa-source/bwa")
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def drop_privileges() -> None:
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    resource.setrlimit(resource.RLIMIT_FSIZE, (32 * 1024 * 1024, 32 * 1024 * 1024))
    os.setgroups([])
    os.setgid(CANDIDATE_GID)
    os.setuid(CANDIDATE_UID)


def run(
    command: list[str | Path],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int = 60,
    candidate: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(value) for value in command],
        cwd=str(cwd),
        env=env,
        text=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
        preexec_fn=drop_privileges if candidate else None,
    )


def root_environment(root: Path) -> dict[str, str]:
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(root),
        "TMPDIR": str(root),
        "LC_ALL": "C.UTF-8",
        "LANG": "C.UTF-8",
        "OMP_NUM_THREADS": "1",
    }


def candidate_environment(root: Path) -> dict[str, str]:
    return {
        **root_environment(root),
        "PYTHONNOUSERSITE": "1",
    }


def prepare_fixtures(matrix: dict[str, Any]):
    fixture_root = Path(tempfile.mkdtemp(prefix="algobridge0010-fixtures-"))
    fixture_root.chmod(0o755)
    cases: dict[str, tuple[Path, dict[str, Any]]] = {}
    for section in ("public", "hidden"):
        for entry in matrix[section]:
            case_id = str(entry["id"])
            case_dir = fixture_root / case_id
            make_fixture(entry["spec"], case_dir)
            parameters = json.loads((case_dir / "parameters.json").read_text(encoding="utf-8"))
            for path in case_dir.rglob("*"):
                if path.is_file():
                    path.chmod(0o444)
            case_dir.chmod(0o755)
            cases[case_id] = (case_dir, parameters)
    return fixture_root, cases


def normalized_mem(binary: Path, case_dir: Path, *, candidate: bool) -> list[str]:
    root = Path(tempfile.mkdtemp(prefix="algobridge0010-legacy-mem-"))
    root.chmod(0o755)
    if candidate:
        os.chown(root, CANDIDATE_UID, CANDIDATE_GID)
    reference = root / "reference.fa"
    reads = root / "reads.fastq"
    shutil.copyfile(case_dir / "reference.fa", reference)
    shutil.copyfile(case_dir / "reads.fastq", reads)
    if candidate:
        os.chown(reference, CANDIDATE_UID, CANDIDATE_GID)
        os.chown(reads, CANDIDATE_UID, CANDIDATE_GID)
    reference.chmod(0o644)
    reads.chmod(0o444)
    env = candidate_environment(root) if candidate else root_environment(root)
    indexed = run([binary, "index", reference], cwd=root, env=env, timeout=60, candidate=candidate)
    if indexed.returncode != 0:
        raise RuntimeError(f"BWA index failed: {indexed.stderr[-4000:]}")
    aligned = run(
        [binary, "mem", "-R", "@RG\\tID:legacy\\tSM:SAMPLE", reference, reads],
        cwd=root,
        env=env,
        timeout=60,
        candidate=candidate,
    )
    if aligned.returncode != 0:
        raise RuntimeError(f"BWA mem failed: {aligned.stderr[-4000:]}")
    return [
        line for line in aligned.stdout.splitlines()
        if line and not line.startswith("@PG")
    ]


def remove_reference_assets() -> dict[str, Any]:
    targets = [
        Path("/opt/reference-freebayes-source"),
        Path("/opt/pristine-bwa-source"),
        Path("/opt/task-inputs"),
        Path("/usr/share/doc/freebayes"),
        Path("/usr/share/doc/bwa"),
        Path("/usr/share/doc/samtools"),
        Path("/usr/share/bwa"),
    ]
    files = [
        Path("/usr/bin/freebayes"),
        Path("/usr/bin/bamleftalign"),
        Path("/usr/bin/bwa"),
        Path("/usr/bin/samtools"),
    ]
    donor_library_patterns = (
        "libtabixpp.so*",
        "libvcflib.so*",
        "libseqlib.so*",
        "libsmithwaterman.so*",
        "libdisorder.so*",
        "libfastahack.so*",
        "libfml.so*",
        "libssw.so*",
    )
    for pattern in donor_library_patterns:
        files.extend(Path("/lib/x86_64-linux-gnu").glob(pattern))
    removed: list[str] = []
    for target in targets:
        if target.exists():
            shutil.rmtree(target)
            removed.append(str(target))
    for target in files:
        if target.exists() or target.is_symlink():
            target.unlink()
            removed.append(str(target))
    leftovers = [str(path) for path in targets + files if path.exists() or path.is_symlink()]
    if leftovers:
        raise RuntimeError(f"reference cleanup failed: {leftovers}")
    for executable in ("freebayes", "bamleftalign", "bwa", "samtools"):
        if shutil.which(executable) is not None:
            raise RuntimeError(f"{executable} remains discoverable in candidate PATH")
    library_leftovers = [
        str(path)
        for pattern in donor_library_patterns
        for path in Path("/lib/x86_64-linux-gnu").glob(pattern)
    ]
    if library_leftovers:
        raise RuntimeError(f"donor libraries remain: {library_leftovers}")
    return {"removed": removed, "reference_tools_in_path": False}


def copy_candidate_tree(stage: Path) -> None:
    skip_names = {".git", "__pycache__", "bwa", "libbwa.a"}
    skip_suffixes = {".o", ".a", ".pyc"}
    for source in TESTBED.rglob("*"):
        relative = source.relative_to(TESTBED)
        if any(part in skip_names for part in relative.parts):
            continue
        if source.is_dir():
            (stage / relative).mkdir(parents=True, exist_ok=True)
        elif source.is_file() and source.suffix not in skip_suffixes:
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for path in sorted(stage.rglob("*"), reverse=True):
        if path.is_dir():
            path.chmod(0o755)
        else:
            path.chmod(0o644)
        os.chown(path, CANDIDATE_UID, CANDIDATE_GID)
    os.chown(stage, CANDIDATE_UID, CANDIDATE_GID)
    stage.chmod(0o755)


def prepare_candidate():
    stage = Path(tempfile.mkdtemp(prefix="algobridge0010-candidate-build-"))
    copy_candidate_tree(stage)
    environment = candidate_environment(stage)
    cleaned = run(["make", "clean"], cwd=stage, env=environment, timeout=60, candidate=True)
    if cleaned.returncode != 0:
        raise RuntimeError(f"candidate make clean failed:\n{cleaned.stderr[-8000:]}")
    built = run(["make", "-j2"], cwd=stage, env=environment, timeout=180, candidate=True)
    if built.returncode != 0:
        raise RuntimeError(f"candidate compilation failed:\n{built.stderr[-8000:]}")
    binary = stage / "bwa"
    if not binary.is_file():
        raise RuntimeError("candidate build did not produce bwa")
    binary.chmod(0o555)
    return stage, binary, {
        "command": ["make", "-j2"],
        "stderr_tail": built.stderr[-4000:],
        "binary_sha256": sha256(binary),
    }


def run_candidate_case(binary: Path, case_dir: Path, parameters: dict[str, Any]):
    root = Path(tempfile.mkdtemp(prefix="algobridge0010-candidate-case-"))
    root.chmod(0o755)
    os.chown(root, CANDIDATE_UID, CANDIDATE_GID)
    reference = root / "reference.fa"
    reads = root / "reads.fastq"
    shutil.copyfile(case_dir / "reference.fa", reference)
    shutil.copyfile(case_dir / "reads.fastq", reads)
    os.chown(reference, CANDIDATE_UID, CANDIDATE_GID)
    os.chown(reads, CANDIDATE_UID, CANDIDATE_GID)
    reference.chmod(0o644)
    reads.chmod(0o444)
    environment = candidate_environment(root)

    indexed = run([binary, "index", reference], cwd=root, env=environment, timeout=60, candidate=True)
    if indexed.returncode != 0:
        raise RuntimeError(f"candidate BWA index failed: {indexed.stderr[-4000:]}")
    sample = str(parameters["sample"])
    aligned = run(
        [binary, "mem", "-R", f"@RG\\tID:rg1\\tSM:{sample}", reference, reads],
        cwd=root,
        env=environment,
        timeout=60,
        candidate=True,
    )
    if aligned.returncode != 0:
        raise RuntimeError(f"candidate BWA mem failed: {aligned.stderr[-4000:]}")
    raw_sam = root / "raw.sam"
    transformed_sam = root / "alignments.sam"
    raw_sam.write_text(aligned.stdout, encoding="ascii")
    rewrite_sam_flags(raw_sam, transformed_sam, parameters)
    raw_sam.chmod(0o444)
    transformed_sam.chmod(0o444)

    command = [
        binary,
        "snv-call",
        "-f", reference,
        "-s", sample,
        "-p", str(int(parameters["ploidy"])),
        "--min-base-quality", str(int(parameters["min_base_quality"])),
        "--min-mapping-quality", str(int(parameters["min_mapping_quality"])),
        "--min-alternate-count", str(int(parameters["min_alternate_count"])),
        "--min-alternate-fraction", format(float(parameters["min_alternate_fraction"]), ".17g"),
        "--theta", format(float(parameters["theta"]), ".17g"),
        transformed_sam,
    ]
    called = run(command, cwd=root, env=environment, timeout=60, candidate=True)
    if called.returncode != 0:
        raise RuntimeError(f"candidate snv-call failed: {called.stderr[-4000:]}")
    if len(called.stdout.encode()) > 8_000_000:
        raise RuntimeError("candidate VCF exceeds 8 MB")
    vcf = root / "candidate.vcf"
    vcf.write_text(called.stdout, encoding="ascii")
    return parse_calls(vcf, sample), called.stderr[-2000:]


def grade() -> dict[str, Any]:
    LOGS.mkdir(parents=True, exist_ok=True)
    matrix = json.loads((TESTS / "case_specs.json").read_text(encoding="utf-8"))
    report: dict[str, Any] = {
        "schema_version": 1,
        "task": "algobridge-0010__bwa__absorbs__freebayes",
        "gates": {},
        "public_cases": [],
        "hidden_cases": [],
    }
    gates = report["gates"]

    source_problems, source_details = check_source_policy(
        TESTBED, Path("/opt/pristine-bwa-source"), Path("/opt/reference-freebayes-source")
    )
    gates["source_policy"] = {
        "passed": not source_problems,
        "problems": source_problems,
        "details": source_details,
    }
    if source_problems:
        report.update(reward=0.0, summary="source policy hard gate failed")
        return report

    fixture_root, cases = prepare_fixtures(matrix)
    references: dict[str, list[dict[str, Any]]] = {}
    for section in ("public", "hidden"):
        for entry in matrix[section]:
            case_id = str(entry["id"])
            case_dir, parameters = cases[case_id]
            references[case_id] = reference_calls(case_dir, parameters)
    first_id = str(matrix["hidden"][0]["id"])
    repeated = reference_calls(cases[first_id][0], cases[first_id][1])
    deterministic = repeated == references[first_id]
    gates["reference_determinism"] = {"passed": deterministic, "case": first_id}
    if not deterministic:
        raise RuntimeError("locked reference workflow is not deterministic")

    legacy_case_id = str(matrix["public"][0]["id"])
    legacy_reference = normalized_mem(PRISTINE_BWA, cases[legacy_case_id][0], candidate=False)
    gates["reference_pipeline"] = {
        "passed": True,
        "workflow": "locked pristine BWA-MEM 0.7.17 -> samtools 1.13 -> real FreeBayes 1.3.6",
        "public_cases": len(matrix["public"]),
        "hidden_cases": len(matrix["hidden"]),
        "pristine_bwa_sha256": sha256(PRISTINE_BWA),
    }

    gates["candidate_isolation"] = {"passed": True, **remove_reference_assets()}
    stage, binary, build = prepare_candidate()
    gates["candidate_build"] = {"passed": True, **build}
    legacy_candidate = normalized_mem(binary, cases[legacy_case_id][0], candidate=True)
    legacy_ok = legacy_candidate == legacy_reference
    gates["legacy_bwa_mem_regression"] = {
        "passed": legacy_ok,
        "reference_line_count": len(legacy_reference),
        "candidate_line_count": len(legacy_candidate),
    }
    if not legacy_ok:
        report.update(reward=0.0, summary="legacy BWA-MEM regression hard gate failed")
        return report

    for section, destination in (("public", "public_cases"), ("hidden", "hidden_cases")):
        for entry in matrix[section]:
            case_id = str(entry["id"])
            case_dir, parameters = cases[case_id]
            try:
                candidate_calls, stderr_tail = run_candidate_case(binary, case_dir, parameters)
                problems = compare_calls(references[case_id], candidate_calls)
                case_report = {
                    "id": case_id,
                    "passed": not problems,
                    "reference_call_count": len(references[case_id]),
                    "candidate_call_count": len(candidate_calls),
                    "problems": problems,
                    "candidate_stderr_tail": stderr_tail,
                }
            except Exception as error:
                case_report = {"id": case_id, "passed": False, "problems": [str(error)]}
            report[destination].append(case_report)

    hidden_passed = sum(bool(item.get("passed")) for item in report["hidden_cases"])
    public_passed = sum(bool(item.get("passed")) for item in report["public_cases"])
    reward = hidden_passed / len(matrix["hidden"])
    report.update(
        reward=reward,
        hidden_passed=hidden_passed,
        public_passed=public_passed,
        summary=(
            f"{hidden_passed}/{len(matrix['hidden'])} hidden differential cases passed; "
            f"{public_passed}/{len(matrix['public'])} public examples passed"
        ),
        candidate_stage=str(stage),
        fixture_root=str(fixture_root),
    )
    return report


def main() -> None:
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        report = grade()
    except Exception as error:
        report = {
            "schema_version": 1,
            "task": "algobridge-0010__bwa__absorbs__freebayes",
            "reward": 0.0,
            "summary": "verifier exception",
            "exception": str(error),
            "traceback": traceback.format_exc(),
        }
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REWARD.write_text(f"{float(report['reward']):.12g}\n", encoding="ascii")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
