#!/usr/bin/env python3
"""Separate offline differential verifier for ALGOBRIDGE-0023."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile

from candidate_runner import run_candidate, run_invalid
from cases import PUBLIC_CASES, hidden_cases, validate_case
from reference_runner import run_reference


TESTBED = Path("/testbed")
PRISTINE = Path("/opt/pristine-host/lammps")
DONOR = Path("/opt/donor-source/mlip-3")
LOCK = Path("/tests/source-lock.json")
REPORT = Path("/logs/verifier/report.json")
REWARD = Path("/logs/verifier/reward.txt")
ALLOWED = {"src/pair_mtp_bounded.cpp", "src/pair_mtp_bounded.h"}


class GateFailure(RuntimeError):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_report(report, reward):
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    report["reward"] = float(reward)
    REPORT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REWARD.write_text(f"{float(reward):.10f}\n", encoding="ascii")


def fail(reason, report=None):
    report = {} if report is None else report
    report.update({"status": "hard_gate_failed", "reason": reason})
    write_report(report, 0.0)
    raise SystemExit(0)


def generated_extra(relative):
    text = relative.as_posix()
    if text.startswith("src/Obj_serial/"):
        return True
    if text in {"src/STUBS/mpi.o", "src/STUBS/libmpi_stubs.a"}:
        return True
    if relative.parent.as_posix() != "src":
        return False
    name = relative.name
    return (
        name in {
            "lmp_serial", "liblammps.a", "liblammps_serial.a", "lmpinstalledpkgs.h",
            "lmpgitversion.h", "tmp_lmpinstalledpkgs.h_name.lmpinstalled",
            "Makefile.package", "Makefile.package.settings",
        }
        or name.endswith(".tmp")
        or (name.startswith("style_") and name.endswith(".h"))
        or (name.startswith("packages_") and name.endswith(".h"))
    )


def token_windows(text, width=64):
    tokens = re.findall(
        r"[A-Za-z_][A-Za-z_0-9]*|(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|[^\s]",
        text,
    )
    return {
        hashlib.sha256("\x1f".join(tokens[index:index + width]).encode()).digest()
        for index in range(max(0, len(tokens) - width + 1))
    }


def source_gate():
    if not TESTBED.is_dir() or not PRISTINE.is_dir():
        raise GateFailure("candidate or pristine LAMMPS tree is missing")
    pristine_files = {}
    for path in PRISTINE.rglob("*"):
        relative = path.relative_to(PRISTINE)
        if path.is_symlink():
            pristine_files[relative] = ("link", os.readlink(path))
        elif path.is_file():
            pristine_files[relative] = ("file", sha256(path))
    for relative, (kind, expected) in pristine_files.items():
        candidate = TESTBED / relative
        if kind == "link":
            if not candidate.is_symlink() or os.readlink(candidate) != expected:
                raise GateFailure(f"locked host symlink changed: {relative}")
        elif not candidate.is_file() or candidate.is_symlink() or sha256(candidate) != expected:
            raise GateFailure(f"locked host file changed or missing: {relative}")

    extras = []
    for path in TESTBED.rglob("*"):
        if not (path.is_file() or path.is_symlink()):
            continue
        relative = path.relative_to(TESTBED)
        if relative in pristine_files or relative.as_posix() in ALLOWED or generated_extra(relative):
            continue
        extras.append(relative.as_posix())
    if extras:
        raise GateFailure(f"unauthorized added files: {extras[:12]}")
    for name in sorted(ALLOWED):
        path = TESTBED / name
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 50000:
            raise GateFailure(f"missing, linked, or oversized candidate source: {name}")
    try:
        source_text = "\n".join((TESTBED / name).read_text(encoding="utf-8")
                                for name in sorted(ALLOWED))
    except UnicodeDecodeError as error:
        raise GateFailure("candidate source is not UTF-8") from error
    if not re.search(r"PairStyle\s*\(\s*mtp_bounded\s*,", source_text):
        raise GateFailure("required PairStyle(mtp_bounded, ...) registration is missing")
    forbidden = {
        "MLIP include": r"#\s*include\s*[<\"][^>\"]*mlip",
        "process launch": r"\b(?:system|popen|fork|execv|execve|posix_spawn)\s*\(",
        "dynamic loading": r"\b(?:dlopen|dlsym)\s*\(",
        "network": r"\b(?:socket|connect|curl|wget)\b",
        "private path": r"/opt/reference|/tests|/solution",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, source_text, flags=re.IGNORECASE):
            raise GateFailure(f"forbidden dependency or access primitive: {label}")
    candidate_windows = token_windows(source_text)
    if candidate_windows:
        for path in DONOR.rglob("*"):
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
                continue
            if path.suffix.lower() not in {".c", ".cc", ".cpp", ".h", ".hpp"}:
                continue
            if candidate_windows & token_windows(path.read_text(encoding="utf-8", errors="ignore")):
                raise GateFailure(f"candidate contains a copied 64-token donor window: {path.name}")
    return {
        "allowed_files": sorted(ALLOWED),
        "candidate_bytes": {name: (TESTBED / name).stat().st_size for name in sorted(ALLOWED)},
        "forbidden_scan": "pass", "donor_window_scan": "pass",
    }


def provenance_gate():
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    checks = {
        "/opt/source-archives/host-source.tar.gz": lock["host"]["archive_sha256"],
        "/opt/source-archives/donor-source.tar.gz": lock["donor"]["archive_sha256"],
        "/opt/reference-mlip/bin/mlp": lock["reference_runtime"]["mlp_sha256"],
        "/opt/reference-mlip/lib/libgfortran.so.5": lock["reference_runtime"]["libgfortran_sha256"],
        "/opt/reference-mlip/lib/libquadmath.so.0": lock["reference_runtime"]["libquadmath_sha256"],
        "/opt/reference-mlip/mtp9-bounded.mtp": lock["potential"]["sha256"],
    }
    for kind in ("host", "donor"):
        for part in lock[kind]["parts"]:
            checks[f"/opt/source-archives/parts/{part['name']}"] = part["sha256"]
    for name, expected in checks.items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            raise GateFailure(f"provenance mismatch: {name}")
    environment = dict(os.environ)
    environment["LD_LIBRARY_PATH"] = "/opt/reference-mlip/lib"
    completed = subprocess.run(
        ["/opt/reference-mlip/bin/mlp", "help"], text=True, capture_output=True,
        timeout=20, check=False, env=environment,
    )
    if completed.returncode or "mlp serial version" not in completed.stdout:
        raise GateFailure("locked MLIP-3 reference runtime smoke check failed")
    return {"authenticated_files": len(checks), "mlip_runtime": "pass"}


def isolation_gate():
    protected = (
        "/tests", "/opt/reference-mlip", "/opt/donor-source",
        "/opt/pristine-host", "/opt/source-archives", "/opt/reference-runner",
    )
    readable = []
    for name in protected:
        completed = subprocess.run(
            ["runuser", "-u", "candidate", "--", "test", "-r", name],
            timeout=10, check=False,
        )
        if completed.returncode == 0:
            readable.append(name)
    if readable:
        raise GateFailure(f"candidate can read protected paths: {readable}")
    return {"uid": 10001, "protected_paths_unreadable": list(protected)}


def build_candidate():
    completed = subprocess.run(
        ["make", "-C", "/testbed/src", "serial", "-j8"],
        text=True, capture_output=True, timeout=900, check=False,
    )
    if completed.returncode:
        raise GateFailure(f"candidate LAMMPS build failed: {completed.stderr[-2500:]}")
    help_run = subprocess.run(
        ["runuser", "-u", "candidate", "--", "/testbed/src/lmp_serial", "-help"],
        text=True, capture_output=True, timeout=30, check=False,
    )
    if help_run.returncode or not re.search(r"\bmtp_bounded\b", help_run.stdout):
        raise GateFailure("built LAMMPS does not register pair_style mtp_bounded")
    return {"binary_sha256": sha256(TESTBED / "src/lmp_serial"), "help_registration": "pass"}


def finite_result(result, atom_count):
    if not isinstance(result, dict) or set(result) != {"energy", "forces", "virial"}:
        return False
    values = [result.get("energy")]
    forces, virial = result.get("forces"), result.get("virial")
    if not isinstance(forces, list) or len(forces) != atom_count:
        return False
    if not isinstance(virial, list) or len(virial) != 6:
        return False
    for vector in forces:
        if not isinstance(vector, list) or len(vector) != 3:
            return False
        values.extend(vector)
    values.extend(virial)
    return all(isinstance(value, (int, float)) and not isinstance(value, bool)
               and math.isfinite(value) for value in values)


def close_scalar(expected, observed, absolute, relative):
    return abs(expected - observed) <= absolute + relative * max(abs(expected), abs(observed))


def component_results(expected, observed):
    energy = close_scalar(expected["energy"], observed["energy"], 2.0e-9, 2.0e-10)
    force = all(close_scalar(left, right, 2.0e-5, 2.0e-6)
                for expected_row, observed_row in zip(expected["forces"], observed["forces"])
                for left, right in zip(expected_row, observed_row))
    virial = all(close_scalar(left, right, 3.0e-4, 3.0e-6)
                  for left, right in zip(expected["virial"], observed["virial"]))
    errors = {
        "energy_abs": abs(expected["energy"] - observed["energy"]),
        "force_max_abs": max(abs(left - right)
                             for expected_row, observed_row in zip(expected["forces"], observed["forces"])
                             for left, right in zip(expected_row, observed_row)),
        "virial_max_abs": max(abs(left - right)
                              for left, right in zip(expected["virial"], observed["virial"])),
    }
    return {"energy": energy, "forces": force, "virial": virial}, errors


def translated(packet):
    result = copy.deepcopy(packet)
    shifts = (0.73, 1.11, 0.49)
    result["name"] += "__translated"
    result["positions"] = [
        [(point[axis] + shifts[axis]) % result["box"][axis] for axis in range(3)]
        for point in result["positions"]
    ]
    return result


def permuted(packet):
    result = copy.deepcopy(packet)
    result["name"] += "__permuted"
    result["positions"] = list(reversed(result["positions"]))
    return result


def exact_identity(left, right, force_permutation=None):
    if not close_scalar(left["energy"], right["energy"], 2.0e-9, 2.0e-10):
        return False
    if not all(close_scalar(a, b, 3.0e-8, 3.0e-9)
               for a, b in zip(left["virial"], right["virial"])):
        return False
    right_forces = right["forces"]
    if force_permutation == "reverse":
        right_forces = list(reversed(right_forces))
    return all(close_scalar(a, b, 3.0e-8, 3.0e-9)
               for left_row, right_row in zip(left["forces"], right_forces)
               for a, b in zip(left_row, right_row))


def main():
    report = {"task": "ALGOBRIDGE-0023"}
    try:
        report["provenance"] = provenance_gate()
        report["source_policy"] = source_gate()
        report["isolation"] = isolation_gate()
        report["build"] = build_candidate()
    except Exception as error:
        fail(f"{type(error).__name__}: {error}", report)

    cases = PUBLIC_CASES + hidden_cases()
    details = []
    passed_components = 0
    total_components = len(cases) * 3
    for packet in cases:
        validate_case(packet)
        try:
            expected = run_reference(packet)
            observed = run_candidate(packet)
            if not finite_result(expected, len(packet["positions"])):
                raise GateFailure("reference produced a malformed result")
            if not finite_result(observed, len(packet["positions"])):
                raise RuntimeError("candidate produced a malformed result")
            components, errors = component_results(expected, observed)
        except GateFailure as error:
            fail(str(error), report)
        except Exception as error:
            components = {"energy": False, "forces": False, "virial": False}
            errors = {"runtime": f"{type(error).__name__}: {error}"}
        passed_components += sum(components.values())
        details.append({"name": packet["name"], "components": components, "errors": errors})

    invalid = {}
    for mode in ("cutoff_mismatch", "two_types", "malformed", "missing"):
        try:
            invalid[mode] = run_invalid(PUBLIC_CASES[2], mode)
        except Exception:
            invalid[mode] = False
    if not all(invalid.values()):
        fail(f"invalid-input rejection failed: {invalid}", report)

    base = PUBLIC_CASES[2]
    try:
        base_result = run_candidate(base)
        translated_result = run_candidate(translated(base))
        permuted_result = run_candidate(permuted(base))
        metamorphic = {
            "translation": exact_identity(base_result, translated_result),
            "atom_permutation": exact_identity(base_result, permuted_result, "reverse"),
        }
    except Exception as error:
        metamorphic = {"translation": False, "atom_permutation": False,
                       "runtime": f"{type(error).__name__}: {error}"}
    if not metamorphic.get("translation") or not metamorphic.get("atom_permutation"):
        fail(f"metamorphic identity failed: {metamorphic}", report)

    reward = passed_components / total_components
    report.update({
        "status": "passed" if passed_components == total_components else "partial",
        "public_cases": len(PUBLIC_CASES), "hidden_cases": len(cases) - len(PUBLIC_CASES),
        "scientific_components_passed": passed_components,
        "scientific_components_total": total_components,
        "invalid_inputs": invalid, "metamorphic": metamorphic, "cases": details,
    })
    write_report(report, reward)


if __name__ == "__main__":
    main()

