#!/usr/bin/env python3
"""Independent differential verifier for ALGOBRIDGE-0024."""

from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import site
import subprocess
import tarfile
import tempfile
import time

import numpy as np

from candidate_runner import run_candidate, run_invalid
from cases import CASES
from model import compare_results, parse_result, scientific_errors
from reference_runner import generate


TESTS = Path("/tests")
TESTBED = Path(os.environ.get("TESTBED_PATH", "/testbed"))
LOGS = Path("/logs/verifier")
REFERENCE_LAMMPS = Path("/opt/reference-lammps/src/lmp_serial")
REFERENCE_SOURCE = Path("/opt/reference-lammps")
DONOR_SOURCE = Path("/opt/reference-phonopy-source")
ALLOWED_CANDIDATE = {"src/fit_harmonic_fc2.cpp", "src/fit_harmonic_fc2.h"}


class GateFailure(RuntimeError):
    pass


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _generated_extra(relative):
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
            "lmp_serial",
            "liblammps.a",
            "liblammps_serial.a",
            "lmpinstalledpkgs.h",
            "lmpgitversion.h",
            "tmp_lmpinstalledpkgs.h_name.lmpinstalled",
            "Makefile.package",
            "Makefile.package.settings",
        }
        or name.endswith(".tmp")
        or (name.startswith("style_") and name.endswith(".h"))
        or (name.startswith("packages_") and name.endswith(".h"))
    )


def _tokens(text):
    return re.findall(r"[A-Za-z_][A-Za-z_0-9]*|(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?|[^\s]", text)


def source_gate(temp_root):
    if not TESTBED.is_dir():
        raise GateFailure("/testbed artifact is missing")
    expected_archive = "a73a74ab6a5c266c13da160ccb7affa809e8d3daa109c597c655a0d4ba88084a"
    if sha256(TESTS / "host-source.tar.gz") != expected_archive:
        raise GateFailure("private host archive hash mismatch")
    pristine_root = temp_root / "pristine"
    pristine_root.mkdir()
    with tarfile.open(TESTS / "host-source.tar.gz", "r:gz") as archive:
        archive.extractall(pristine_root)
    pristine = pristine_root / "lammps"

    pristine_files = {}
    for path in pristine.rglob("*"):
        if path.is_symlink():
            pristine_files[path.relative_to(pristine)] = ("link", os.readlink(path))
        elif path.is_file():
            pristine_files[path.relative_to(pristine)] = ("file", sha256(path))
    for relative, (kind, expected) in pristine_files.items():
        candidate = TESTBED / relative
        if kind == "link":
            if not candidate.is_symlink() or os.readlink(candidate) != expected:
                raise GateFailure(f"host source symlink changed: {relative}")
        else:
            if not candidate.is_file() or candidate.is_symlink():
                raise GateFailure(f"host source file missing: {relative}")
            if sha256(candidate) != expected:
                raise GateFailure(f"host source file changed: {relative}")

    extras = []
    generated = []
    for path in TESTBED.rglob("*"):
        if not (path.is_file() or path.is_symlink()):
            continue
        relative = path.relative_to(TESTBED)
        if relative in pristine_files:
            continue
        text = relative.as_posix()
        if text in ALLOWED_CANDIDATE:
            continue
        if _generated_extra(relative):
            generated.append(path)
            continue
        extras.append(text)
    missing_candidate = [name for name in sorted(ALLOWED_CANDIDATE) if not (TESTBED / name).is_file()]
    if missing_candidate:
        raise GateFailure(f"required candidate source missing: {missing_candidate}")
    if extras:
        raise GateFailure(f"unauthorized added files: {extras[:12]}")

    source_text = "\n".join((TESTBED / name).read_text(encoding="utf-8", errors="replace") for name in sorted(ALLOWED_CANDIDATE))
    forbidden = {
        "donor name": r"\bphonopy\b",
        "NumPy": r"\bnumpy\b|Python\.h",
        "SciPy": r"\bscipy\b",
        "process launch": r"\b(?:system|popen|fork|execv|execve|posix_spawn)\s*\(",
        "dynamic loading": r"\b(?:dlopen|dlsym)\s*\(",
        "network": r"\b(?:socket|connect|curl|wget)\b",
        "private path": r"/opt/reference|/tests|/solution",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, source_text, flags=re.IGNORECASE):
            raise GateFailure(f"forbidden dependency/process token: {label}")

    candidate_tokens = _tokens(source_text)
    window = 64
    candidate_windows = {
        hashlib.sha256("\x1f".join(candidate_tokens[index : index + window]).encode()).digest()
        for index in range(max(0, len(candidate_tokens) - window + 1))
    }
    if candidate_windows:
        for donor_file in DONOR_SOURCE.rglob("*"):
            if donor_file.suffix.lower() not in {".py", ".c", ".h", ".cpp", ".rs"} or not donor_file.is_file():
                continue
            donor_tokens = _tokens(donor_file.read_text(encoding="utf-8", errors="ignore"))
            for index in range(max(0, len(donor_tokens) - window + 1)):
                digest = hashlib.sha256("\x1f".join(donor_tokens[index : index + window]).encode()).digest()
                if digest in candidate_windows:
                    raise GateFailure(f"candidate contains a {window}-token donor fragment")
    return generated, {
        "pristine_files_checked": len(pristine_files),
        "candidate_cpp_sha256": sha256(TESTBED / "src/fit_harmonic_fc2.cpp"),
        "candidate_header_sha256": sha256(TESTBED / "src/fit_harmonic_fc2.h"),
        "donor_fragment_window": window,
    }


def remove_generated(generated):
    for path in sorted(generated, key=lambda item: len(item.parts), reverse=True):
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    shutil.rmtree(TESTBED / "src/Obj_serial", ignore_errors=True)
    for path in (TESTBED / "src/STUBS").glob("*.o"):
        path.unlink(missing_ok=True)
    (TESTBED / "src/STUBS/libmpi_stubs.a").unlink(missing_ok=True)


def remove_reference_assets():
    shutil.rmtree(REFERENCE_SOURCE, ignore_errors=True)
    shutil.rmtree(DONOR_SOURCE, ignore_errors=True)
    for root in site.getsitepackages():
        root_path = Path(root)
        for pattern in ("phonopy", "phonopy-*", "phonors", "phonors-*"):
            for path in root_path.glob(pattern):
                if path.is_dir() and not path.is_symlink():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)
    for module_name in list(__import__("sys").modules):
        if module_name == "phonopy" or module_name.startswith("phonopy.") or module_name == "phonors":
            del __import__("sys").modules[module_name]


def build_candidate():
    process = subprocess.run(
        ["make", "-C", str(TESTBED / "src"), "serial", "-j8"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=900,
        check=False,
        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/nonexistent"},
    )
    if process.returncode != 0:
        raise GateFailure(f"candidate build failed:\n{process.stdout[-6000:]}")
    executable = TESTBED / "src/lmp_serial"
    if not executable.is_file():
        raise GateFailure("candidate build did not create lmp_serial")
    ldd = subprocess.run(["ldd", str(executable)], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    lowered = ldd.stdout.lower()
    if any(token in lowered for token in ("phonopy", "python", "numpy", "scipy")):
        raise GateFailure(f"candidate binary has a forbidden dynamic dependency:\n{ldd.stdout}")
    return executable, process.stdout[-3000:], ldd.stdout


def host_regression(executable, root):
    help_run = subprocess.run(
        [str(executable), "-help"], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30, check=False
    )
    if help_run.returncode != 0 or "Large-scale Atomic/Molecular" not in help_run.stdout or "fit_harmonic_fc2" not in help_run.stdout:
        raise GateFailure("LAMMPS help/version/command registration regression")
    script = root / "host-regression.in"
    script.write_text(
        "units lj\natom_style atomic\nboundary p p p\n"
        "region box block 0 2 0 2 0 2\ncreate_box 1 box\n"
        "create_atoms 1 single 0.5 0.5 0.5\nmass 1 1\n"
        "pair_style zero 1.0\npair_coeff * *\nrun 0\n",
        encoding="utf-8",
    )
    run = subprocess.run(
        [str(executable), "-log", "none", "-screen", "none", "-in", str(script)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
        check=False,
    )
    if run.returncode != 0:
        raise GateFailure(f"upstream LAMMPS smoke regression failed: {run.stdout[-2000:]}")


def invalid_variants(base):
    variants = []
    item = copy.deepcopy(base); item["format"] = "wrong"; variants.append(("format", item))
    item = copy.deepcopy(base); item["frequency_factor"] = 0; variants.append(("frequency", item))
    item = copy.deepcopy(base); item["symmetrize_iterations"] = 0; variants.append(("iterations", item))
    item = copy.deepcopy(base); item["supercell"]["masses"][0] = 0; variants.append(("mass", item))
    item = copy.deepcopy(base); item["qpoints"] = []; variants.append(("qpoints", item))
    item = copy.deepcopy(base); item["records"][0]["forces"] = item["records"][0]["forces"][:-1]; variants.append(("force_shape", item))
    item = copy.deepcopy(base); item["records"][0]["displacement"] = [0.1, 0, 0]; variants.append(("displacement", item))
    item = copy.deepcopy(base); item["records"] = [record for record in item["records"] if record["atom"] == 0]; variants.append(("missing_atom", item))
    item = copy.deepcopy(base)
    for record in item["records"]:
        sign = -1.0 if record["displacement"][0] < 0 else 1.0
        record["displacement"] = [sign * 0.004, 0, 0]
    variants.append(("rank_deficient", item))
    item = copy.deepcopy(base); item["qpoints"][0] = ["not-a-number", 0, 0]; variants.append(("non_numeric", item))
    item = copy.deepcopy(base)
    term = copy.deepcopy(item["supercell"]["phase_links"][0][0][0])
    item["supercell"]["phase_links"][0][0].append(term)
    variants.append(("duplicate_phase_atom", item))
    return variants


def permute_supercell(candidate_input, reference):
    transformed = copy.deepcopy(candidate_input)
    n = transformed["supercell"]["n_atoms"]
    new_to_old = list(reversed(range(n)))
    old_to_new = {old: new for new, old in enumerate(new_to_old)}
    for key in ("scaled_positions", "symbols"):
        transformed["supercell"][key] = [transformed["supercell"][key][old] for old in new_to_old]
    transformed["supercell"]["p2s_map"] = [old_to_new[old] for old in transformed["supercell"]["p2s_map"]]
    for row in transformed["supercell"]["phase_links"]:
        for terms in row:
            for term in terms:
                term["force_atom"] = old_to_new[term["force_atom"]]
    for record in transformed["records"]:
        record["atom"] = old_to_new[record["atom"]]
        record["forces"] = [record["forces"][old] for old in new_to_old]
    expected = copy.deepcopy(reference)
    fc = np.asarray(reference["force_constants"])
    expected["force_constants"] = fc[np.ix_(new_to_old, new_to_old)].tolist()
    return transformed, expected


def rotate_coordinates(candidate_input, reference):
    transformed = copy.deepcopy(candidate_input)
    rotation = np.asarray([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])
    cell = np.asarray(transformed["supercell"]["cell"], dtype=float)
    transformed["supercell"]["cell"] = (cell @ rotation.T).tolist()
    for record in transformed["records"]:
        record["displacement"] = (rotation @ np.asarray(record["displacement"], dtype=float)).tolist()
        record["forces"] = (np.asarray(record["forces"], dtype=float) @ rotation.T).tolist()
    expected = copy.deepcopy(reference)
    fc = np.asarray(reference["force_constants"], dtype=float)
    expected["force_constants"] = np.einsum("ac,ijcd,bd->ijab", rotation, fc, rotation).tolist()
    primitive = transformed["supercell"]["n_primitive"]
    block_rotation = np.kron(np.eye(primitive), rotation)
    for item in expected["qpoint_results"]:
        dm = np.asarray(item["dynamical_matrix_real"]) + 1j * np.asarray(item["dynamical_matrix_imag"])
        vectors = np.asarray(item["eigenvectors_real"]) + 1j * np.asarray(item["eigenvectors_imag"])
        dm = block_rotation @ dm @ block_rotation.T
        vectors = block_rotation @ vectors
        item["dynamical_matrix_real"] = dm.real.tolist()
        item["dynamical_matrix_imag"] = dm.imag.tolist()
        item["eigenvectors_real"] = vectors.real.tolist()
        item["eigenvectors_imag"] = vectors.imag.tolist()
    return transformed, expected


def scale_forces(candidate_input, reference, factor=4.0):
    transformed = copy.deepcopy(candidate_input)
    for record in transformed["records"]:
        record["forces"] = (np.asarray(record["forces"], dtype=float) * factor).tolist()
    expected = copy.deepcopy(reference)
    expected["force_constants"] = (np.asarray(expected["force_constants"]) * factor).tolist()
    for key in ("fit_residual_rms", "asr_max", "permutation_max"):
        expected[key] *= factor
    for item in expected["qpoint_results"]:
        for key in ("dynamical_matrix_real", "dynamical_matrix_imag", "eigenvalues"):
            item[key] = (np.asarray(item[key]) * factor).tolist()
        item["frequencies"] = (np.asarray(item["frequencies"]) * np.sqrt(factor)).tolist()
    return transformed, expected


def make_read_only(root, executable):
    for path in root.rglob("*"):
        if path.is_dir():
            path.chmod(0o555)
        elif path.is_file():
            path.chmod(0o444)
    executable.chmod(0o555)
    root.chmod(0o555)


def write_result(reward, report):
    LOGS.mkdir(parents=True, exist_ok=True)
    (LOGS / "reward.txt").write_text(f"{reward:.12g}\n", encoding="utf-8")
    (LOGS / "report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    started = time.time()
    report = {"task": "algobridge-0024__lammps__absorbs__phonopy", "hard_gates": {}, "cases": []}
    temp_root = Path(tempfile.mkdtemp(prefix="algobridge0024-grader-"))
    # tempfile creates the root as 0700. Candidate processes deliberately run
    # as uid/gid 10001, so keep the contents private but allow path traversal.
    temp_root.chmod(0o711)
    try:
        generated, source_info = source_gate(temp_root)
        report["hard_gates"]["source_integrity"] = {"passed": True, **source_info}

        references = []
        reference_root = temp_root / "reference"
        reference_root.mkdir()
        for case in CASES:
            case_root = reference_root / case["name"]
            case_root.mkdir()
            candidate_input, reference = generate(case, REFERENCE_LAMMPS, case_root)
            references.append((case, candidate_input, reference))
        report["hard_gates"]["real_reference"] = {
            "passed": True,
            "cases": len(references),
            "lammps_executable_sha256": sha256(REFERENCE_LAMMPS),
            "pipeline": "pristine LAMMPS finite-displacement forces -> pristine phonopy traditional FC2",
        }

        remove_reference_assets()
        if REFERENCE_SOURCE.exists() or DONOR_SOURCE.exists():
            raise GateFailure("reference source removal failed")
        report["hard_gates"]["donor_absence"] = {"passed": True}

        remove_generated(generated)
        executable, build_tail, ldd = build_candidate()
        report["hard_gates"]["clean_rebuild"] = {"passed": True, "build_tail": build_tail, "ldd": ldd}
        host_regression(executable, temp_root)
        report["hard_gates"]["host_regression"] = {"passed": True}
        make_read_only(TESTBED, executable)
        os.chmod(TESTS, 0o700)

        invalid_results = []
        for name, invalid in invalid_variants(references[0][1]):
            passed, output = run_invalid(executable, invalid, temp_root / "invalid" / name)
            invalid_results.append({"name": name, "passed": passed, "tail": output[-500:]})
            if not passed:
                raise GateFailure(f"invalid input was not rejected atomically: {name}")
        report["hard_gates"]["invalid_inputs"] = {"passed": True, "checks": invalid_results}

        candidate_baselines = {}
        for case, candidate_input, reference in references:
            try:
                candidate, _ = run_candidate(
                    executable, candidate_input, temp_root / "candidate" / case["name"]
                )
                passed, errors, metrics = compare_results(reference, candidate, candidate_input)
                candidate_baselines[case["name"]] = candidate
            except Exception as exc:
                passed, errors, metrics = False, [str(exc)], {}
            report["cases"].append(
                {"name": case["name"], "passed": passed, "errors": errors, "metrics": metrics}
            )

        cross_checks = []
        by_name = {case["name"]: (candidate_input, reference) for case, candidate_input, reference in references}

        base_input, base_reference = by_name["mono_chain_four"]
        reordered = copy.deepcopy(base_input)
        reordered["records"] = list(reversed(reordered["records"]))
        got, _ = run_candidate(executable, reordered, temp_root / "cross" / "record_order")
        passed, errors, metrics = compare_results(base_reference, got, reordered)
        cross_checks.append({"name": "record_order", "passed": passed, "errors": errors, "metrics": metrics})

        transformed, expected = permute_supercell(base_input, base_reference)
        got, _ = run_candidate(executable, transformed, temp_root / "cross" / "atom_reorder")
        passed, errors, metrics = compare_results(expected, got, transformed)
        cross_checks.append({"name": "atom_reorder", "passed": passed, "errors": errors, "metrics": metrics})

        diatomic_input, diatomic_reference = by_name["diatomic_chain"]
        transformed, expected = rotate_coordinates(diatomic_input, diatomic_reference)
        got, _ = run_candidate(executable, transformed, temp_root / "cross" / "rotation")
        passed, errors, metrics = compare_results(expected, got, transformed)
        cross_checks.append({"name": "coordinate_rotation", "passed": passed, "errors": errors, "metrics": metrics})

        transformed, expected = scale_forces(diatomic_input, diatomic_reference)
        got, _ = run_candidate(executable, transformed, temp_root / "cross" / "force_scaling")
        passed, errors, metrics = compare_results(expected, got, transformed)
        cross_checks.append({"name": "force_scaling", "passed": passed, "errors": errors, "metrics": metrics})

        periodic = copy.deepcopy(base_input)
        expected = copy.deepcopy(base_reference)
        for qpoint, expected_item in zip(periodic["qpoints"], expected["qpoint_results"], strict=True):
            qpoint[0] += 1.0
            expected_item["qpoint"] = qpoint
        got, _ = run_candidate(executable, periodic, temp_root / "cross" / "q_periodicity")
        passed, errors, metrics = compare_results(expected, got, periodic)
        cross_checks.append({"name": "q_periodicity", "passed": passed, "errors": errors, "metrics": metrics})

        report["hard_gates"]["cross_invariants"] = {"passed": all(item["passed"] for item in cross_checks), "checks": cross_checks}
        if not report["hard_gates"]["cross_invariants"]["passed"]:
            raise GateFailure("one or more cross-input scientific invariants failed")

        passed_cases = sum(item["passed"] for item in report["cases"])
        reward = passed_cases / len(report["cases"])
        report["summary"] = {
            "passed": passed_cases,
            "total": len(report["cases"]),
            "reward": reward,
            "elapsed_sec": time.time() - started,
        }
        write_result(reward, report)
    except Exception as exc:
        report["fatal_error"] = str(exc)
        report["summary"] = {
            "passed": 0,
            "total": len(CASES),
            "reward": 0.0,
            "elapsed_sec": time.time() - started,
        }
        write_result(0.0, report)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    main()
