#!/usr/bin/env python3
"""Isolated differential grader for the AlphaFold 2 / DockQ task.

The locked donor is used only by the root verifier while producing ephemeral
reference values.  It is then physically removed before any candidate code is
compiled, imported, or executed.  Candidate work always runs as uid/gid 10001
through a root-owned runner which contains fixtures, but never reference values.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import json
import math
import os
import pickle
import random
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np


TESTBED = Path("/testbed")
TARGET = TESTBED / "alphafold/common/dockq_score.py"
RUN_ALPHAFOLD = TESTBED / "run_alphafold.py"
REFERENCE_ROOT = Path("/tests/reference")
DOCKQ_SOURCE = REFERENCE_ROOT / "dockq/src"
LOG_DIR = Path("/logs/verifier")
REWARD_PATH = LOG_DIR / "reward.txt"
RESULTS_PATH = LOG_DIR / "grader-results.json"
HOST_MANIFEST = Path("/tests/host-files.sha256")
RUNNER_DIR = Path("/opt/candidate-runner")
RUNNER_PATH = RUNNER_DIR / "runner.py"
REAL_E2E_RUNNER_SOURCE = Path("/tests/real_e2e_runner.py")
REAL_E2E_INSPECT_SOURCE = Path("/tests/real_e2e_inspect.py")
REAL_E2E_RUNNER = RUNNER_DIR / "real_e2e_runner.py"
REAL_E2E_INSPECT = RUNNER_DIR / "real_e2e_inspect.py"
REAL_E2E_DATA = Path("/opt/af2-e2e-data")
PRISTINE_AF2_ROOT = REFERENCE_ROOT / "alphafold-source"
REAL_E2E_FASTA_NAME = "hidden_real_multimer"
REAL_E2E_MODEL_NAME = "model_1_multimer_v3_pred_0"
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
DOCKQ_COMMIT = "75db7ab4f6b824c70d120c5f620582e164ed5479"
ATOL = 5e-4
RTOL = 5e-4
TOTAL_CASES = 15
E2E_ONE_TO_THREE = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS",
    "Q": "GLN", "E": "GLU", "G": "GLY", "H": "HIS", "I": "ILE",
    "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE", "P": "PRO",
    "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL",
}
SCIENTIFIC_KEYS = {
    "fnat", "iRMSD", "LRMSD", "DockQ", "CAPRI",
    "native_contacts", "preserved_contacts", "mapping",
}
WORKFLOW_KEYS = {
    "status", "reason", "dockq", "fnat", "irms", "lrms", "capri",
    "native_contacts", "preserved_contacts", "mapping",
}


def residue(name: str, center: tuple[float, float, float]) -> dict[str, Any]:
    x, y, z = center
    return {
        "name": name,
        "atoms": {
            "N": [x - 1.2, y, z],
            "CA": [x, y, z],
            "C": [x + 1.3, y, z],
            "O": [x + 1.8, y + 0.5, z],
            "CB": [x, y + 1.1, z + 0.7],
        },
    }


def chain(names: list[str], y: float, z: float = 0.0) -> list[dict[str, Any]]:
    return [
        residue(name, (index * 3.8, y, z))
        for index, name in enumerate(names)
    ]


def transform(
    structure: dict[str, Any],
    rotation: list[list[float]],
    translation: list[float],
) -> dict[str, Any]:
    result = copy.deepcopy(structure)
    rotation_array = np.asarray(rotation, dtype=float)
    translation_array = np.asarray(translation, dtype=float)
    for residues in result["chains"].values():
        for item in residues:
            for atom_name, coord in item["atoms"].items():
                item["atoms"][atom_name] = (
                    np.asarray(coord) @ rotation_array + translation_array
                ).tolist()
    return result


def perturb_chain(
    structure: dict[str, Any], chain_id: str, vector: list[float]
) -> dict[str, Any]:
    result = copy.deepcopy(structure)
    delta = np.asarray(vector, dtype=float)
    for item in result["chains"][chain_id]:
        for atom_name, coord in item["atoms"].items():
            item["atoms"][atom_name] = (np.asarray(coord) + delta).tolist()
    return result


def _pdb(structure: dict[str, Any]) -> str:
    lines = ["MODEL     1"]
    serial = 1
    for chain_id, residues in structure["chains"].items():
        for resid, residue_data in enumerate(residues, 1):
            for atom_name, coord in residue_data["atoms"].items():
                x, y, z = coord
                shown = atom_name if len(atom_name) == 4 else f" {atom_name}"
                lines.append(
                    f"ATOM  {serial:5d} {shown:<4} {residue_data['name']:>3} "
                    f"{chain_id:1}{resid:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
                    f"{1.0:6.2f}{0.0:6.2f}          {atom_name[0]:>2}  "
                )
                serial += 1
        lines.append(
            f"TER   {serial:5d}      {residues[-1]['name']:>3} "
            f"{chain_id:1}{len(residues):4d}"
        )
        serial += 1
    lines.extend(["ENDMDL", "END"])
    return "\n".join(line.ljust(80) for line in lines) + "\n"


def _parse_pdb(text: str) -> dict[str, Any]:
    chains: dict[str, list[dict[str, Any]]] = {}
    residue_keys: dict[tuple[str, int], dict[str, Any]] = {}
    for line in text.splitlines():
        if not line.startswith("ATOM"):
            continue
        atom_name = line[12:16].strip()
        residue_name = line[17:20].strip()
        chain_id = line[21].strip() or "A"
        residue_id = int(line[22:26])
        coord = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
        key = (chain_id, residue_id)
        if key not in residue_keys:
            item: dict[str, Any] = {"name": residue_name, "atoms": {}}
            chains.setdefault(chain_id, []).append(item)
            residue_keys[key] = item
        residue_keys[key]["atoms"][atom_name] = coord
    return {"chains": chains}


def _canonical(structure: dict[str, Any]) -> dict[str, Any]:
    """Apply the same three-decimal PDB quantization seen by locked DockQ."""
    return _parse_pdb(_pdb(structure))


def _capri(score: float) -> str:
    if score >= 0.80:
        return "high"
    if score >= 0.49:
        return "medium"
    if score >= 0.23:
        return "acceptable"
    return "incorrect"


def build_cases() -> list[dict[str, Any]]:
    rng = random.Random(1729)
    native = {
        "chains": {
            "A": chain(["ALA", "GLY", "SER", "LEU", "ASN"], 0.0),
            "B": chain(["TYR", "VAL", "ASP"], 4.2),
        }
    }
    angle = 0.63
    rotation = [
        [math.cos(angle), -math.sin(angle), 0.0],
        [math.sin(angle), math.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ]
    swapped = {
        "chains": {
            "X": copy.deepcopy(native["chains"]["B"]),
            "Y": copy.deepcopy(native["chains"]["A"]),
        }
    }
    ambiguous_native = {
        "chains": {
            "A": chain(["ALA", "GLY", "SER", "LEU"], 0.0),
            "B": chain(["ALA", "GLY", "SER", "LEU"], 4.2),
        }
    }
    ambiguous_model = {
        "chains": {
            "X": copy.deepcopy(ambiguous_native["chains"]["B"]),
            "Y": copy.deepcopy(ambiguous_native["chains"]["A"]),
        }
    }
    random_models = [
        perturb_chain(
            native,
            "B",
            [
                rng.uniform(-0.5, 0.5),
                rng.uniform(0.2, 2.4),
                rng.uniform(-0.8, 0.8),
            ],
        )
        for _ in range(4)
    ]
    rigid = transform(
        native,
        [[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]],
        [4.0, 9.0, -2.0],
    )
    definitions: list[tuple[str, str, dict[str, Any], dict[str, str] | None]] = [
        ("identity", "scientific", native, None),
        (
            "explicit_mapping_perturbation",
            "scientific",
            perturb_chain(native, "B", [0.3, 1.1, -0.4]),
            {"A": "A", "B": "B"},
        ),
        (
            "rotated_distorted_complex",
            "scientific",
            transform(
                perturb_chain(native, "B", [0.0, 2.6, 0.2]),
                rotation,
                [11.0, -3.0, 7.0],
            ),
            None,
        ),
        ("sequence_mapped_chain_swap", "scientific", swapped, None),
        ("seeded_perturbation_1", "scientific", random_models[0], None),
        ("seeded_perturbation_2", "scientific", random_models[1], None),
        ("seeded_perturbation_3", "scientific", random_models[2], None),
        (
            "ambiguous_sequence_mapping_search",
            "scientific",
            ambiguous_model,
            None,
        ),
        ("rigid_body_invariance", "scientific", rigid, None),
        (
            "standalone_json_cli",
            "cli",
            perturb_chain(native, "B", [-0.27, 1.43, 0.51]),
            None,
        ),
        (
            "alphafold_cli_and_signature_contract",
            "workflow",
            perturb_chain(native, "B", [0.21, 0.72, -0.36]),
            None,
        ),
        (
            "real_h200_official_pipeline_and_model",
            "real_e2e",
            transform(
                perturb_chain(native, "B", [0.18, 1.87, 0.31]),
                rotation,
                [2.0, -5.0, 1.0],
            ),
            None,
        ),
        (
            "real_upstream_prediction_equivalence",
            "real_e2e",
            perturb_chain(native, "B", [-0.12, 0.93, -0.29]),
            None,
        ),
        (
            "real_integrated_dockq_differential",
            "real_e2e",
            perturb_chain(native, "B", [0.41, 1.22, 0.12]),
            None,
        ),
        (
            "real_alphafold_artifact_integration",
            "real_e2e",
            perturb_chain(native, "B", [-0.33, 2.08, 0.47]),
            None,
        ),
    ]
    cases = []
    canonical_native = _canonical(native)
    for index, (name, category, model, mapping) in enumerate(definitions, 1):
        current = {
            "index": index,
            "name": name,
            "category": category,
            "model": _canonical(model),
            "native": copy.deepcopy(canonical_native),
            "mapping": mapping,
        }
        if name == "ambiguous_sequence_mapping_search":
            current["native"] = _canonical(ambiguous_native)
            current["reference_mappings"] = [
                {"X": "A", "Y": "B"},
                {"X": "B", "Y": "A"},
            ]
        cases.append(current)
    if len(cases) != TOTAL_CASES:
        raise RuntimeError(f"internal case-count error: {len(cases)}")
    return cases


def dockq_reference(case: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute the unmodified locked DockQ implementation for one case."""
    with tempfile.TemporaryDirectory(prefix="dockq-reference-") as temp_name:
        temp = Path(temp_name)
        model_path = temp / "model.pdb"
        native_path = temp / "native.pdb"
        model_text = _pdb(case["model"])
        native_text = _pdb(case["native"])
        model_path.write_text(model_text, encoding="utf-8")
        native_path.write_text(native_text, encoding="utf-8")
        env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": f"{REFERENCE_ROOT / 'shims'}:{DOCKQ_SOURCE}",
            "HOME": temp_name,
            "TMPDIR": temp_name,
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
        reference_mappings = case.get("reference_mappings", [case["mapping"]])
        results = []
        for mapping_index, mapping in enumerate(reference_mappings):
            output_path = temp / f"dockq-{mapping_index}.json"
            command = [
                sys.executable,
                str(REFERENCE_ROOT / "reference_runner.py"),
                str(model_path),
                str(native_path),
                str(output_path),
            ]
            if mapping:
                model_ids = sorted(mapping)
                command.append(
                    "".join(model_ids)
                    + ":"
                    + "".join(mapping[key] for key in model_ids)
                )
            completed = subprocess.run(
                command,
                env=env,
                cwd=temp_name,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            if completed.returncode != 0:
                detail = (completed.stderr or completed.stdout).strip()[-1200:]
                raise RuntimeError(
                    f"locked DockQ failed for case {case['index']} "
                    f"mapping {mapping_index} with exit {completed.returncode}: {detail}"
                )
            pair = json.loads(output_path.read_text(encoding="utf-8"))
            chain_map = pair["chain_map"]
            result = {
                "fnat": float(pair["fnat"]),
                "iRMSD": float(pair["iRMSD"]),
                "LRMSD": float(pair["LRMSD"]),
                "DockQ": float(pair["DockQ"]),
                "CAPRI": _capri(float(pair["DockQ"])),
                "native_contacts": int(pair["nat_total"]),
                "preserved_contacts": int(pair["nat_correct"]),
                "mapping": {
                    str(model_id): str(native_id)
                    for native_id, model_id in chain_map.items()
                },
            }
            results.append(result)
        result = sorted(
            results,
            key=lambda item: (
                -item["DockQ"],
                json.dumps(item["mapping"], sort_keys=True),
            ),
        )[0]
        evidence = {
            "case_index": case["index"],
            "locked_mapping_runs": len(reference_mappings),
            "model_pdb_sha256": hashlib.sha256(model_text.encode()).hexdigest(),
            "native_pdb_sha256": hashlib.sha256(native_text.encode()).hexdigest(),
            "reference_result_sha256": hashlib.sha256(
                json.dumps(result, sort_keys=True).encode()
            ).hexdigest(),
        }
        return result, evidence


def _dockq_reference_files(model_path: Path, native_path: Path) -> dict[str, Any]:
    """Run locked original DockQ on two concrete PDB files."""
    with tempfile.TemporaryDirectory(prefix="dockq-real-e2e-") as temp_name:
        output_path = Path(temp_name) / "dockq.json"
        env = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": f"{REFERENCE_ROOT / 'shims'}:{DOCKQ_SOURCE}",
            "HOME": temp_name,
            "TMPDIR": temp_name,
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
        completed = subprocess.run(
            [
                sys.executable,
                str(REFERENCE_ROOT / "reference_runner.py"),
                str(model_path),
                str(native_path),
                str(output_path),
            ],
            env=env,
            cwd=temp_name,
            text=True,
            capture_output=True,
            timeout=60,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[-1600:]
            raise RuntimeError(
                "locked DockQ failed on real AF2 output: "
                f"exit {completed.returncode}: {detail}"
            )
        pair = json.loads(output_path.read_text(encoding="utf-8"))
        chain_map = pair["chain_map"]
        score = float(pair["DockQ"])
        return {
            "fnat": float(pair["fnat"]),
            "iRMSD": float(pair["iRMSD"]),
            "LRMSD": float(pair["LRMSD"]),
            "DockQ": score,
            "CAPRI": _capri(score),
            "native_contacts": int(pair["nat_total"]),
            "preserved_contacts": int(pair["nat_correct"]),
            "mapping": {
                str(model_id): str(native_id)
                for native_id, model_id in chain_map.items()
            },
        }


def _real_e2e_fixture() -> tuple[str, str]:
    sequence_a = "ACDEFGHIKLMN"
    sequence_b = "QRSTVWYACD"
    native = {
        "chains": {
            "A": chain([E2E_ONE_TO_THREE[item] for item in sequence_a], 0.0),
            "B": chain([E2E_ONE_TO_THREE[item] for item in sequence_b], 4.2),
        }
    }
    fasta = (
        f">hidden_chain_A\n{sequence_a}\n"
        f">hidden_chain_B\n{sequence_b}\n"
    )
    return fasta, _pdb(native)


def _real_e2e_env(home: Path) -> dict[str, str]:
    env = {
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "TMPDIR": str(home),
        "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "2",
        "XLA_PYTHON_CLIENT_PREALLOCATE": "false",
        "TF_CPP_MIN_LOG_LEVEL": "2",
        "JAX_COMPILATION_CACHE_DIR": "/tmp/af2-e2e-jax-cache",
    }
    for name in (
        "CUDA_VISIBLE_DEVICES",
        "LD_LIBRARY_PATH",
        "XLA_FLAGS",
        "NVIDIA_VISIBLE_DEVICES",
        "NVIDIA_DRIVER_CAPABILITIES",
    ):
        if os.environ.get(name):
            env[name] = os.environ[name]
    return env


def _real_e2e_command(
    runner_path: Path,
    source_root: Path,
    fasta_path: Path,
    native_path: Path,
    output_root: Path,
    fixture_root: Path,
    metadata_path: Path,
    integrated: bool,
) -> list[str]:
    command = [
        sys.executable,
        "-I",
        "-B",
        str(runner_path),
        "--source-root",
        str(source_root),
        "--fasta-path",
        str(fasta_path),
        "--fasta-name",
        REAL_E2E_FASTA_NAME,
        "--native-path",
        str(native_path),
        "--output-root",
        str(output_root),
        "--fixture-root",
        str(fixture_root),
        "--data-root",
        str(REAL_E2E_DATA),
        "--metadata-path",
        str(metadata_path),
        "--tool-dir",
        "/usr/bin",
    ]
    if integrated:
        command.append("--integrated")
    return command


def _run_real_e2e_reference() -> dict[str, Any]:
    """Run pristine locked AF2 then locked original DockQ before donor removal."""
    if not PRISTINE_AF2_ROOT.is_dir():
        raise RuntimeError("pristine locked AlphaFold source is missing from verifier")
    params = REAL_E2E_DATA / "params" / "params_model_1_multimer_v3.npz"
    if not params.is_file():
        raise RuntimeError("real E2E model parameters are missing")
    expected_params_hash = "611da8fc7478928f68de12e8b226260ef1f4ce62bcc29b008572e52f4f212959"
    if hashlib.sha256(params.read_bytes()).hexdigest() != expected_params_hash:
        raise RuntimeError("real E2E model parameters failed SHA-256 integrity check")

    cache = Path("/tmp/af2-e2e-jax-cache")
    cache.mkdir(parents=True, exist_ok=True)
    os.chmod(cache, 0o777)
    work = Path(tempfile.mkdtemp(prefix="af2-real-reference-", dir="/tmp"))
    os.chmod(work, 0o700)
    fasta_text, native_text = _real_e2e_fixture()
    fasta_path = work / "hidden.fasta"
    native_path = work / "native.pdb"
    fasta_path.write_text(fasta_text, encoding="utf-8")
    native_path.write_text(native_text, encoding="utf-8")
    output_root = work / "output"
    fixture_root = work / "pipeline-inputs"
    metadata_path = work / "metadata.json"
    command = _real_e2e_command(
        REAL_E2E_RUNNER_SOURCE,
        PRISTINE_AF2_ROOT,
        fasta_path,
        native_path,
        output_root,
        fixture_root,
        metadata_path,
        integrated=False,
    )
    completed = subprocess.run(
        command,
        cwd=work,
        env=_real_e2e_env(work),
        text=True,
        capture_output=True,
        timeout=420,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-2400:]
        raise RuntimeError(
            f"pristine real AlphaFold E2E failed with exit {completed.returncode}: {detail}"
        )

    output_dir = output_root / REAL_E2E_FASTA_NAME
    pdb_path = output_dir / f"unrelaxed_{REAL_E2E_MODEL_NAME}.pdb"
    result_path = output_dir / f"result_{REAL_E2E_MODEL_NAME}.pkl"
    if not pdb_path.is_file() or not result_path.is_file():
        raise RuntimeError("pristine real AlphaFold output is incomplete")
    with result_path.open("rb") as handle:
        original_result = pickle.load(handle)
    ranking = json.loads(
        (output_dir / "ranking_debug.json").read_text(encoding="utf-8")
    )
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    dockq = _dockq_reference_files(pdb_path, native_path)
    pdb_bytes = pdb_path.read_bytes()
    return {
        "fasta_text": fasta_text,
        "native_text": native_text,
        "pdb_sha256": hashlib.sha256(pdb_bytes).hexdigest(),
        "pdb_size": len(pdb_bytes),
        "ranking": ranking,
        "result_keys": sorted(str(key) for key in original_result),
        "metadata": metadata,
        "dockq": dockq,
        "evidence": {
            "locked_af2_commit": "c77e5d2a8961d1a353632c462914ff0a32a950f6",
            "model_params_sha256": expected_params_hash,
            "model_name": "model_1_multimer_v3",
            "num_recycle": 1,
            "sequence_lengths": [12, 10],
            "reference_prediction_pdb_sha256": hashlib.sha256(pdb_bytes).hexdigest(),
            "reference_dockq_sha256": hashlib.sha256(
                json.dumps(dockq, sort_keys=True).encode()
            ).hexdigest(),
            "jax_devices": metadata.get("jax_devices"),
            "elapsed_seconds": metadata.get("elapsed_seconds"),
        },
    }


def _candidate_setpriv_prefix() -> list[str]:
    return [
        "/usr/bin/setpriv",
        f"--reuid={CANDIDATE_UID}",
        f"--regid={CANDIDATE_GID}",
        "--clear-groups",
        "--no-new-privs",
        "--inh-caps=-all",
        "--ambient-caps=-all",
        "--bounding-set=-all",
    ]


def _run_real_e2e_candidate(reference: dict[str, Any]) -> dict[str, Any]:
    """Run the candidate through the same real GPU pipeline after donor removal."""
    work = Path(tempfile.mkdtemp(prefix="af2-real-candidate-", dir="/tmp"))
    os.chown(work, CANDIDATE_UID, CANDIDATE_GID)
    os.chmod(work, 0o700)
    try:
        fasta_path = work / "hidden.fasta"
        native_path = work / "native.pdb"
        fasta_path.write_text(reference["fasta_text"], encoding="utf-8")
        native_path.write_text(reference["native_text"], encoding="utf-8")
        for path in (fasta_path, native_path):
            os.chown(path, CANDIDATE_UID, CANDIDATE_GID)
            os.chmod(path, 0o600)
        output_root = work / "output"
        fixture_root = work / "pipeline-inputs"
        metadata_path = work / "metadata.json"
        command = _candidate_setpriv_prefix() + _real_e2e_command(
            REAL_E2E_RUNNER,
            TESTBED,
            fasta_path,
            native_path,
            output_root,
            fixture_root,
            metadata_path,
            integrated=True,
        )
        try:
            completed = subprocess.run(
                command,
                cwd=work,
                env=_real_e2e_env(work),
                text=True,
                capture_output=True,
                timeout=420,
                check=False,
            )
        finally:
            _kill_candidate_processes()
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout).strip()[-2400:]
            raise RuntimeError(
                f"candidate real AlphaFold E2E exited {completed.returncode}: {detail}"
            )

        output_dir = output_root / REAL_E2E_FASTA_NAME
        observation_path = work / "observation.json"
        inspect_command = _candidate_setpriv_prefix() + [
            sys.executable,
            "-I",
            "-B",
            str(REAL_E2E_INSPECT),
            "--output-dir",
            str(output_dir),
            "--runner-name",
            REAL_E2E_MODEL_NAME,
            "--result-path",
            str(observation_path),
        ]
        try:
            inspected = subprocess.run(
                inspect_command,
                cwd=work,
                env=_real_e2e_env(work),
                text=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
        finally:
            _kill_candidate_processes()
        if inspected.returncode != 0 or not observation_path.is_file():
            detail = (inspected.stderr or inspected.stdout).strip()[-1600:]
            raise RuntimeError(f"candidate real output inspection failed: {detail}")
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        pdb_path = output_dir / f"unrelaxed_{REAL_E2E_MODEL_NAME}.pdb"
        if pdb_path.is_symlink() or not pdb_path.is_file():
            raise RuntimeError("candidate real unrelaxed PDB is missing or is a symlink")
        if pdb_path.stat().st_size <= 0 or pdb_path.stat().st_size > 10_000_000:
            raise RuntimeError("candidate real unrelaxed PDB has an invalid size")
        pdb_sha256 = hashlib.sha256(pdb_path.read_bytes()).hexdigest()
        return {
            "metadata": metadata,
            "observation": observation,
            "pdb_sha256": pdb_sha256,
            "prediction_equivalent": (
                pdb_sha256 == reference["pdb_sha256"]
                and observation.get("ranking") == reference["ranking"]
            ),
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _donor_fingerprints() -> dict[str, set[str]]:
    byte_hashes: set[str] = set()
    ast_hashes: set[str] = set()
    for path in sorted((DOCKQ_SOURCE / "DockQ").glob("*.py")):
        data = path.read_bytes()
        byte_hashes.add(hashlib.sha256(data).hexdigest())
        try:
            tree = ast.parse(data.decode("utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        ast_hashes.add(
            hashlib.sha256(
                ast.dump(tree, annotate_fields=True, include_attributes=False).encode()
            ).hexdigest()
        )
    if not byte_hashes:
        raise RuntimeError("locked donor source fingerprints are unavailable")
    return {"bytes": byte_hashes, "ast": ast_hashes}


CANDIDATE_RUNNER = r'''#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import enum
import importlib.util
import inspect
import json
import os
import pickle
import subprocess
import sys
import tempfile
import time
import types
from pathlib import Path
from typing import Any

import numpy as np

TARGET = Path("/testbed/alphafold/common/dockq_score.py")
RUN_ALPHAFOLD = Path("/testbed/run_alphafold.py")
EXPECTED_UID = 10001
RESTYPES = list("ARNDCQEGHILKMFPSTWYV")
RESTYPE_1TO3 = {
    "A": "ALA", "R": "ARG", "N": "ASN", "D": "ASP", "C": "CYS",
    "Q": "GLN", "E": "GLU", "G": "GLY", "H": "HIS", "I": "ILE",
    "L": "LEU", "K": "LYS", "M": "MET", "F": "PHE", "P": "PRO",
    "S": "SER", "T": "THR", "W": "TRP", "Y": "TYR", "V": "VAL",
}
THREE_TO_ONE = {value: key for key, value in RESTYPE_1TO3.items()}
ATOM_NAMES = ("N", "CA", "C", "O", "CB")
ATOM_ORDER = {name: index for index, name in enumerate(ATOM_NAMES)}


class ModelsToRelax(enum.Enum):
    ALL = 0
    BEST = 1
    NONE = 2


def jsonable(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def load_candidate():
    if os.geteuid() != EXPECTED_UID or os.getegid() != EXPECTED_UID:
        raise RuntimeError("candidate runner did not drop privileges")
    if not TARGET.is_file():
        raise FileNotFoundError(f"missing required implementation: {TARGET}")
    source = TARGET.read_text(encoding="utf-8")
    compile(source, str(TARGET), "exec")
    spec = importlib.util.spec_from_file_location("candidate_impl", TARGET)
    if spec is None or spec.loader is None:
        raise ImportError("could not construct candidate module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    function = getattr(module, "score_complex", None)
    if not callable(function):
        raise AssertionError("score_complex is missing or not callable")
    signature = inspect.signature(function)
    expected_names = [
        "model", "native", "mapping", "contact_cutoff", "interface_cutoff"
    ]
    if list(signature.parameters) != expected_names:
        raise AssertionError("score_complex parameter names do not match contract")
    parameters = list(signature.parameters.values())
    if any(
        item.kind not in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
        for item in parameters
    ):
        raise AssertionError("score_complex parameters must accept positional calls")
    if parameters[0].default is not inspect.Parameter.empty:
        raise AssertionError("model must be required")
    if parameters[1].default is not inspect.Parameter.empty:
        raise AssertionError("native must be required")
    if parameters[2].default is not None:
        raise AssertionError("mapping default must be None")
    if parameters[3].default != 5.0:
        raise AssertionError("contact_cutoff default must be 5.0")
    if parameters[4].default != 10.0:
        raise AssertionError("interface_cutoff default must be 10.0")
    return module


def pdb_text(structure):
    lines = ["MODEL     1"]
    serial = 1
    for chain_id, residues in structure["chains"].items():
        for resid, residue_data in enumerate(residues, 1):
            for atom_name, coord in residue_data["atoms"].items():
                x, y, z = coord
                shown = atom_name if len(atom_name) == 4 else f" {atom_name}"
                lines.append(
                    f"ATOM  {serial:5d} {shown:<4} {residue_data['name']:>3} "
                    f"{chain_id:1}{resid:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
                    f"{1.0:6.2f}{0.0:6.2f}          {atom_name[0]:>2}  "
                )
                serial += 1
        lines.append(
            f"TER   {serial:5d}      {residues[-1]['name']:>3} "
            f"{chain_id:1}{len(residues):4d}"
        )
        serial += 1
    lines.extend(["ENDMDL", "END"])
    return "\n".join(line.ljust(80) for line in lines) + "\n"


def parse_pdb(text):
    chains = {}
    residue_keys = {}
    for line in text.splitlines():
        if not line.startswith("ATOM"):
            continue
        atom_name = line[12:16].strip()
        residue_name = line[17:20].strip()
        chain_id = line[21].strip() or "A"
        residue_id = int(line[22:26])
        coord = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
        key = (chain_id, residue_id)
        if key not in residue_keys:
            item = {"name": residue_name, "atoms": {}}
            chains.setdefault(chain_id, []).append(item)
            residue_keys[key] = item
        residue_keys[key]["atoms"][atom_name] = coord
    return {"chains": chains}


def bounded_to_protein(structure):
    positions, masks, aatypes, chain_indices = [], [], [], []
    for chain_index, (_chain_id, residues) in enumerate(structure["chains"].items()):
        for item in residues:
            coords = np.zeros((len(ATOM_NAMES), 3), dtype=float)
            mask = np.zeros(len(ATOM_NAMES), dtype=float)
            for atom_name, coord in item["atoms"].items():
                if atom_name in ATOM_ORDER:
                    coords[ATOM_ORDER[atom_name]] = coord
                    mask[ATOM_ORDER[atom_name]] = 1.0
            positions.append(coords)
            masks.append(mask)
            one_letter = THREE_TO_ONE.get(item["name"], "X")
            aatypes.append(RESTYPES.index(one_letter) if one_letter in RESTYPES else 20)
            chain_indices.append(chain_index)
    return types.SimpleNamespace(
        atom_positions=np.asarray(positions),
        atom_mask=np.asarray(masks),
        aatype=np.asarray(aatypes),
        chain_index=np.asarray(chain_indices),
    )


def protein_to_bounded(prot):
    chains = {}
    restypes = RESTYPES + ["X"]
    for index in range(len(prot.aatype)):
        chain_id = chr(ord("A") + int(prot.chain_index[index]))
        one_letter = restypes[int(prot.aatype[index])]
        residue_name = RESTYPE_1TO3.get(one_letter, "UNK")
        atoms = {}
        for atom_name, atom_index in ATOM_ORDER.items():
            if prot.atom_mask[index, atom_index] >= 0.5:
                atoms[atom_name] = [
                    float(value) for value in prot.atom_positions[index, atom_index]
                ]
        chains.setdefault(chain_id, []).append(
            {"name": residue_name, "atoms": atoms}
        )
    return {"chains": chains}


class FakeDataPipeline:
    def __init__(self):
        self.calls = []

    def process(self, input_fasta_path, msa_output_dir):
        self.calls.append([str(input_fasta_path), str(msa_output_dir)])
        return {"feature": np.asarray([1.0])}


class FakeRunner:
    multimer_mode = True

    def __init__(self, fixture_index, confidence):
        self.fixture_index = fixture_index
        self.confidence = confidence
        self.process_seeds = []
        self.predict_seeds = []

    def process_features(self, feature_dict, random_seed):
        del feature_dict
        self.process_seeds.append(int(random_seed))
        return {"fixture_index": self.fixture_index}

    def predict(self, processed_feature_dict, random_seed):
        self.predict_seeds.append(int(random_seed))
        return {
            "plddt": np.asarray([80.0, 82.0]),
            "ranking_confidence": self.confidence,
            "fixture_index": processed_feature_dict["fixture_index"],
            "legacy_output": np.asarray([7, 11]),
        }


def function_closure(tree):
    definitions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    if "predict_structure" not in definitions:
        raise AssertionError("predict_structure is missing")
    externally_stubbed = {
        "_jnp_to_np", "_save_confidence_json_file", "_save_pae_json_file",
        "_save_mmcif_file",
    }
    wanted = {"predict_structure"}
    changed = True
    while changed:
        changed = False
        for name in tuple(wanted):
            for node in ast.walk(definitions[name]):
                if (
                    isinstance(node, ast.Name)
                    and isinstance(node.ctx, ast.Load)
                    and node.id in definitions
                    and node.id not in externally_stubbed
                    and node.id not in wanted
                ):
                    wanted.add(node.id)
                    changed = True
    return [definitions[name] for name in definitions if name in wanted]


def load_predict_structure(candidate, structures):
    source = RUN_ALPHAFOLD.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RUN_ALPHAFOLD))
    selected = function_closure(tree)

    residue_constants_module = types.ModuleType("alphafold.common.residue_constants")
    residue_constants_module.atom_type_num = len(ATOM_NAMES)
    residue_constants_module.atom_order = ATOM_ORDER
    residue_constants_module.restypes = RESTYPES
    residue_constants_module.restype_1to3 = RESTYPE_1TO3
    alphafold_module = types.ModuleType("alphafold")
    alphafold_module.__path__ = []
    common_module = types.ModuleType("alphafold.common")
    common_module.__path__ = []
    common_module.residue_constants = residue_constants_module
    common_module.dockq_score = candidate
    alphafold_module.common = common_module
    sys.modules["alphafold"] = alphafold_module
    sys.modules["alphafold.common"] = common_module
    sys.modules[residue_constants_module.__name__] = residue_constants_module
    sys.modules["alphafold.common.dockq_score"] = candidate

    class ProteinApi:
        @staticmethod
        def from_prediction(features, result, b_factors, remove_leading_feature_dimension):
            del features, b_factors, remove_leading_feature_dimension
            return bounded_to_protein(structures[int(result["fixture_index"])])

        @staticmethod
        def to_pdb(prot):
            return pdb_text(protein_to_bounded(prot))

        @staticmethod
        def from_pdb_string(text):
            return bounded_to_protein(parse_pdb(text))

        @staticmethod
        def to_mmcif(prot, file_id, model_type):
            del prot, file_id, model_type
            return "data_stub\n"

    def jnp_to_np(value):
        result = {}
        for key, item in value.items():
            if isinstance(item, dict):
                result[key] = jnp_to_np(item)
            else:
                result[key] = item
        return result

    def save_confidence(_plddt, output_dir, model_name):
        Path(output_dir, f"confidence_{model_name}.json").write_text(
            "{}\n", encoding="utf-8"
        )

    def save_pae(_pae, _max_pae, output_dir, model_name):
        Path(output_dir, f"pae_{model_name}.json").write_text(
            "{}\n", encoding="utf-8"
        )

    def save_mmcif(prot, output_dir, model_name, file_id, model_type):
        del prot, file_id, model_type
        Path(output_dir, f"{model_name}.cif").write_text(
            "data_stub\n", encoding="utf-8"
        )

    namespace = {
        "Any": Any,
        "Dict": dict,
        "Union": object,
        "Optional": object,
        "ModelsToRelax": ModelsToRelax,
        "json": json,
        "os": os,
        "pathlib": types.SimpleNamespace(Path=Path),
        "pickle": pickle,
        "time": time,
        "np": np,
        "protein": ProteinApi,
        "residue_constants": residue_constants_module,
        "_jnp_to_np": jnp_to_np,
        "_save_confidence_json_file": save_confidence,
        "_save_pae_json_file": save_pae,
        "_save_mmcif_file": save_mmcif,
        "logging": types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
    }
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(RUN_ALPHAFOLD), "exec"), namespace)
    return namespace["predict_structure"]


def inspect_workflow_contract():
    tree = ast.parse(RUN_ALPHAFOLD.read_text(encoding="utf-8"), filename=str(RUN_ALPHAFOLD))
    dockq_path_flag = False
    run_dockq_flag = False
    main_passes_path = False
    main_passes_switch = False
    signature_has_path = False
    signature_has_switch = False
    path_default_none = False
    switch_default_true = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            function_name = None
            if isinstance(node.func, ast.Attribute):
                function_name = node.func.attr
            if node.args and isinstance(node.args[0], ast.Constant):
                flag_name = node.args[0].value
                if flag_name == "dockq_native_path" and function_name == "DEFINE_string":
                    dockq_path_flag = True
                    if len(node.args) >= 2:
                        path_default_none = (
                            isinstance(node.args[1], ast.Constant)
                            and node.args[1].value is None
                        )
                if flag_name == "run_dockq" and function_name == "DEFINE_boolean":
                    run_dockq_flag = True
                    if len(node.args) >= 2:
                        switch_default_true = (
                            isinstance(node.args[1], ast.Constant)
                            and node.args[1].value is True
                        )
            if isinstance(node.func, ast.Name) and node.func.id == "predict_structure":
                keywords = {item.arg: item.value for item in node.keywords if item.arg}
                main_passes_path = "dockq_native_path" in keywords
                main_passes_switch = "run_dockq" in keywords
    prediction = next(
        (
            node for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == "predict_structure"
        ),
        None,
    )
    if prediction is not None:
        positional = prediction.args.args
        positional_defaults = [None] * (len(positional) - len(prediction.args.defaults)) + list(
            prediction.args.defaults
        )
        entries = list(zip(positional, positional_defaults)) + list(
            zip(prediction.args.kwonlyargs, prediction.args.kw_defaults)
        )
        for argument, default in entries:
            if argument.arg == "dockq_native_path":
                signature_has_path = True
                path_default_none = path_default_none and (
                    isinstance(default, ast.Constant) and default.value is None
                )
            if argument.arg == "run_dockq":
                signature_has_switch = True
                switch_default_true = switch_default_true and (
                    isinstance(default, ast.Constant) and default.value is True
                )
    return {
        "dockq_native_path_flag": dockq_path_flag,
        "run_dockq_flag": run_dockq_flag,
        "dockq_native_path_default_none": path_default_none,
        "run_dockq_default_true": switch_default_true,
        "predict_signature_has_dockq_native_path": signature_has_path,
        "predict_signature_has_run_dockq": signature_has_switch,
        "main_passes_dockq_native_path": main_passes_path,
        "main_passes_run_dockq": main_passes_switch,
    }


def run_pipeline(candidate, payload, include_dockq_kwargs):
    structures = payload["models"]
    predict_structure = load_predict_structure(candidate, structures)
    with tempfile.TemporaryDirectory(prefix="pipeline-") as temp_name:
        temp = Path(temp_name)
        fasta = temp / "fixture.fasta"
        fasta.write_text(">fixture\nAAAA\n", encoding="utf-8")
        native_path = None
        if payload.get("native_text") is not None:
            native_path = temp / "native.pdb"
            native_path.write_text(payload["native_text"], encoding="utf-8")
        data_pipeline = FakeDataPipeline()
        runners = {
            "model_alpha": FakeRunner(0, 0.9),
            "model_beta": FakeRunner(1, 0.8),
        }
        arguments = {
            "fasta_path": str(fasta),
            "fasta_name": "fixture",
            "output_dir_base": str(temp),
            "data_pipeline": data_pipeline,
            "model_runners": runners,
            "amber_relaxer": None,
            "benchmark": False,
            "random_seed": 3,
            "models_to_relax": ModelsToRelax.NONE,
            "model_type": "Multimer",
        }
        if include_dockq_kwargs:
            arguments["dockq_native_path"] = (
                str(native_path) if native_path is not None else None
            )
            arguments["run_dockq"] = bool(payload["run_dockq"])
        caught = None
        try:
            predict_structure(**arguments)
        except Exception as exc:
            caught = {"type": type(exc).__name__, "message": str(exc)[:800]}
        output = temp / "fixture"
        summary_path = output / "dockq_scores.json"
        summary = None
        summary_nonstandard = False
        if summary_path.is_file():
            text = summary_path.read_text(encoding="utf-8")
            summary_nonstandard = "NaN" in text or "Infinity" in text
            try:
                summary = json.loads(text)
            except Exception:
                summary = {"__invalid_json__": True}
        model_outputs = {}
        for model_name in runners:
            result_path = output / f"result_{model_name}.pkl"
            pdb_path = output / f"unrelaxed_{model_name}.pdb"
            item = {
                "result_exists": result_path.is_file(),
                "pdb_exists": pdb_path.is_file() and pdb_path.stat().st_size > 0,
                "confidence_exists": (output / f"confidence_{model_name}.json").is_file(),
                "unrelaxed_mmcif_exists": (output / f"unrelaxed_{model_name}.cif").is_file(),
                "legacy_output": None,
                "dockq_evaluation": None,
            }
            if result_path.is_file():
                try:
                    with result_path.open("rb") as handle:
                        result = pickle.load(handle)
                    item["legacy_output"] = jsonable(result.get("legacy_output"))
                    item["dockq_evaluation"] = jsonable(result.get("dockq_evaluation"))
                except Exception as exc:
                    item["pickle_error"] = f"{type(exc).__name__}: {exc}"[:800]
            model_outputs[model_name] = item
        ranking = None
        ranking_path = output / "ranking_debug.json"
        if ranking_path.is_file():
            try:
                ranking = json.loads(ranking_path.read_text(encoding="utf-8"))
            except Exception:
                ranking = {"__invalid_json__": True}
        timings = None
        timings_path = output / "timings.json"
        if timings_path.is_file():
            try:
                timings = json.loads(timings_path.read_text(encoding="utf-8"))
            except Exception:
                timings = {"__invalid_json__": True}
        return {
            "caught": caught,
            "summary": jsonable(summary),
            "summary_exists": summary_path.is_file(),
            "summary_nonstandard_json": summary_nonstandard,
            "model_outputs": model_outputs,
            "standard_artifacts": {
                "features": (output / "features.pkl").is_file(),
                "ranking": ranking_path.is_file(),
                "timings": timings_path.is_file(),
                "ranked_0": (output / "ranked_0.pdb").is_file(),
                "ranked_1": (output / "ranked_1.pdb").is_file(),
                "ranked_mmcif_0": (output / "ranked_0.cif").is_file(),
                "ranked_mmcif_1": (output / "ranked_1.cif").is_file(),
            },
            "ranking": ranking,
            "timings": timings,
            "data_pipeline_calls": data_pipeline.calls,
            "runner_calls": {
                name: {
                    "process_seeds": runner.process_seeds,
                    "predict_seeds": runner.predict_seeds,
                }
                for name, runner in runners.items()
            },
        }


def run_cli(payload):
    with tempfile.TemporaryDirectory(prefix="cli-") as temp_name:
        temp = Path(temp_name)
        model_path = temp / "model.json"
        native_path = temp / "native.json"
        output_path = temp / "output.json"
        model_path.write_text(json.dumps(payload["model"]), encoding="utf-8")
        native_path.write_text(json.dumps(payload["native"]), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable, str(TARGET), "--model", str(model_path),
                "--native", str(native_path), "--output", str(output_path),
            ],
            cwd=temp_name,
            env={
                "PATH": "/usr/bin:/bin",
                "HOME": temp_name,
                "TMPDIR": temp_name,
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
            },
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        value = None
        nonstandard = False
        if output_path.is_file() and output_path.stat().st_size <= 5_000_000:
            text = output_path.read_text(encoding="utf-8")
            nonstandard = "NaN" in text or "Infinity" in text
            try:
                value = json.loads(text)
            except Exception:
                value = {"__invalid_json__": True}
        return {
            "returncode": completed.returncode,
            "output_exists": output_path.is_file(),
            "nonstandard_json": nonstandard,
            "value": jsonable(value),
            "stderr": completed.stderr[-800:],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    result_path = Path(args.result)
    try:
        payload = json.loads(Path(args.payload).read_text(encoding="utf-8"))
        candidate = load_candidate()
        if args.mode == "gate_import":
            value = {"signature": str(inspect.signature(candidate.score_complex))}
        elif args.mode == "direct":
            value = candidate.score_complex(
                payload["model"], payload["native"], payload.get("mapping")
            )
        elif args.mode == "cli":
            value = run_cli(payload)
        elif args.mode == "workflow_contract":
            value = inspect_workflow_contract()
        elif args.mode == "pipeline":
            value = run_pipeline(candidate, payload, include_dockq_kwargs=True)
        elif args.mode == "host_regression":
            value = run_pipeline(candidate, payload, include_dockq_kwargs=False)
        else:
            raise ValueError(f"unknown mode: {args.mode}")
        envelope = {"ok": True, "value": jsonable(value)}
    except Exception as exc:
        envelope = {
            "ok": False,
            "error_type": type(exc).__name__,
            "error": str(exc)[:1200],
        }
    result_path.write_text(
        json.dumps(envelope, sort_keys=True, allow_nan=False), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
'''


def _install_runner() -> None:
    RUNNER_DIR.mkdir(parents=True, exist_ok=True)
    os.chown(RUNNER_DIR, 0, 0)
    os.chmod(RUNNER_DIR, 0o755)
    RUNNER_PATH.write_text(CANDIDATE_RUNNER, encoding="utf-8")
    shutil.copyfile(REAL_E2E_RUNNER_SOURCE, REAL_E2E_RUNNER)
    shutil.copyfile(REAL_E2E_INSPECT_SOURCE, REAL_E2E_INSPECT)
    for path in (RUNNER_PATH, REAL_E2E_RUNNER, REAL_E2E_INSPECT):
        os.chown(path, 0, 0)
        os.chmod(path, 0o555)


def _remove_reference_and_lock_tests() -> dict[str, Any]:
    if REFERENCE_ROOT.is_symlink():
        REFERENCE_ROOT.unlink()
    elif REFERENCE_ROOT.exists():
        shutil.rmtree(REFERENCE_ROOT)
    os.chown("/tests", 0, 0)
    os.chmod("/tests", 0o700)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    # Preserve the owner of Harbor's host-mounted verifier directory.  Mode
    # 0700 still excludes the uid-10001 candidate during execution, while the
    # host owner must remain able to create reward.json after the container exits.
    os.chmod(LOG_DIR, 0o700)
    return {
        "reference_removed": not REFERENCE_ROOT.exists(),
        "tests_mode": stat.S_IMODE(os.stat("/tests").st_mode),
        "logs_mode": stat.S_IMODE(LOG_DIR.stat().st_mode),
        "candidate_uid": CANDIDATE_UID,
        "candidate_gid": CANDIDATE_GID,
    }


def _ast_digest(tree: ast.AST) -> str:
    return hashlib.sha256(
        ast.dump(tree, annotate_fields=True, include_attributes=False).encode()
    ).hexdigest()


def _forbidden_gate(donor_hashes: dict[str, set[str]]) -> None:
    forbidden_imports = {
        "dockq", "vina", "autodock_vina", "requests", "urllib",
        "subprocess", "socket", "http", "ftplib", "ctypes",
    }
    for path in (TARGET, RUN_ALPHAFOLD):
        if not path.is_file():
            raise AssertionError(f"missing required file: {path}")
        if path.is_symlink():
            raise AssertionError(f"required file may not be a symlink: {path}")
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0].lower() for alias in node.names}
                bad = sorted(roots & forbidden_imports)
                if bad:
                    raise AssertionError(
                        f"forbidden donor/runtime import in {path.name}: {', '.join(bad)}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0].lower()
                if root in forbidden_imports:
                    raise AssertionError(
                        f"forbidden donor/runtime import in {path.name}: {root}"
                    )
            elif isinstance(node, ast.Call):
                if (
                    isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                    and node.func.attr in {"system", "popen", "spawnl", "spawnv"}
                ):
                    raise AssertionError(
                        f"forbidden runtime delegation in {path.name}: os.{node.func.attr}"
                    )
                if isinstance(node.func, ast.Name) and node.func.id == "__import__":
                    raise AssertionError(
                        f"dynamic imports are forbidden in graded integration files: {path.name}"
                    )
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                normalized = node.value.replace("\\", "/").lower()
                if normalized.startswith(("/tests", "/reference", "/opt/dockq")):
                    raise AssertionError(
                        f"forbidden verifier/donor path embedded in {path.name}"
                    )

    for path in TESTBED.rglob("*.py"):
        if not path.is_file() or path.is_symlink():
            continue
        try:
            data = path.read_bytes()
        except OSError:
            continue
        digest = hashlib.sha256(data).hexdigest()
        if digest in donor_hashes["bytes"] and data:
            raise AssertionError(f"vendored locked DockQ source detected: {path}")
        try:
            tree = ast.parse(data.decode("utf-8"), filename=str(path))
        except (SyntaxError, UnicodeDecodeError):
            continue
        if _ast_digest(tree) in donor_hashes["ast"] and tree.body:
            raise AssertionError(f"vendored locked DockQ AST detected: {path}")


def _compile_gate() -> None:
    for path in (TARGET, RUN_ALPHAFOLD):
        if not path.is_file():
            raise AssertionError(f"missing required file: {path}")
        source = path.read_text(encoding="utf-8")
        compile(source, str(path), "exec")


def _host_tree_integrity_gate() -> None:
    """Allow exactly the two task-authorized AlphaFold source changes."""
    if not HOST_MANIFEST.is_file():
        raise RuntimeError("locked AlphaFold host manifest is missing")
    expected: dict[Path, str] = {}
    for line_number, line in enumerate(
        HOST_MANIFEST.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        try:
            digest, relative_text = line.split(maxsplit=1)
        except ValueError as exc:
            raise RuntimeError(
                f"invalid host manifest line {line_number}"
            ) from exc
        relative = Path(relative_text.removeprefix("./"))
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError(
                f"unsafe host manifest path on line {line_number}"
            )
        expected[relative] = digest

    for relative, expected_digest in expected.items():
        path = TESTBED / relative
        if not path.is_file() or path.is_symlink():
            raise AssertionError(f"locked AlphaFold file missing or replaced: {relative}")
        actual_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual_digest != expected_digest:
            raise AssertionError(f"locked AlphaFold file modified: {relative}")

    allowed_changes = {
        Path("run_alphafold.py"),
        Path("alphafold/common/dockq_score.py"),
    }
    actual = set()
    for path in TESTBED.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(TESTBED)
        if "__pycache__" in relative.parts or path.suffix == ".pyc":
            continue
        actual.add(relative)
    extras = sorted(actual - set(expected) - allowed_changes, key=str)
    if extras:
        shown = ", ".join(str(path) for path in extras[:8])
        raise AssertionError(f"unauthorized files added to AlphaFold tree: {shown}")
    for relative in allowed_changes:
        path = TESTBED / relative
        if not path.is_file() or path.is_symlink():
            raise AssertionError(f"required integration file missing or replaced: {relative}")


def _kill_candidate_processes() -> None:
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            lines = (entry / "status").read_text(encoding="utf-8").splitlines()
            uid_line = next(line for line in lines if line.startswith("Uid:"))
            real_uid = int(uid_line.split()[1])
            if real_uid == CANDIDATE_UID:
                os.kill(int(entry.name), signal.SIGKILL)
        except (FileNotFoundError, ProcessLookupError, PermissionError, StopIteration):
            continue


def _invoke_candidate(mode: str, payload: dict[str, Any], timeout: int = 25) -> dict[str, Any]:
    work = Path(tempfile.mkdtemp(prefix="candidate-case-", dir="/tmp"))
    try:
        os.chown(work, CANDIDATE_UID, CANDIDATE_GID)
        os.chmod(work, 0o700)
        payload_path = work / "payload.json"
        result_path = work / "observed.json"
        payload_path.write_text(
            json.dumps(payload, sort_keys=True, allow_nan=False), encoding="utf-8"
        )
        os.chown(payload_path, CANDIDATE_UID, CANDIDATE_GID)
        os.chmod(payload_path, 0o600)
        python = "/usr/bin/python3" if Path("/usr/bin/python3").exists() else sys.executable
        command = [
            "/usr/bin/setpriv",
            f"--reuid={CANDIDATE_UID}",
            f"--regid={CANDIDATE_GID}",
            "--clear-groups",
            "--no-new-privs",
            "--inh-caps=-all",
            "--ambient-caps=-all",
            "--bounding-set=-all",
            python,
            "-I",
            "-B",
            str(RUNNER_PATH),
            "--mode",
            mode,
            "--payload",
            str(payload_path),
            "--result",
            str(result_path),
        ]
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(work),
            "TMPDIR": str(work),
            "PYTHONNOUSERSITE": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
        try:
            completed = subprocess.run(
                command,
                cwd=work,
                env=env,
                text=True,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        finally:
            _kill_candidate_processes()
        if completed.returncode != 0:
            diagnostic = (completed.stderr or completed.stdout).strip()[-1200:]
            return {
                "ok": False,
                "error_type": "CandidateProcessError",
                "error": f"candidate runner exited {completed.returncode}: {diagnostic}",
            }
        if not result_path.is_file():
            return {
                "ok": False,
                "error_type": "MissingResult",
                "error": "candidate runner did not produce an observation",
            }
        if result_path.stat().st_size > 10_000_000:
            return {
                "ok": False,
                "error_type": "OversizedResult",
                "error": "candidate observation exceeded 10 MB",
            }
        try:
            return json.loads(result_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return {
                "ok": False,
                "error_type": type(exc).__name__,
                "error": "candidate observation was not valid JSON",
            }
    except subprocess.TimeoutExpired:
        _kill_candidate_processes()
        return {
            "ok": False,
            "error_type": "TimeoutExpired",
            "error": f"candidate phase exceeded {timeout} seconds",
        }
    finally:
        shutil.rmtree(work, ignore_errors=True)


def _compare(actual: Any, expected: Any, path: str = "result") -> None:
    if isinstance(expected, bool) or isinstance(actual, bool):
        if actual is not expected:
            raise AssertionError(f"boolean mismatch at {path}")
        return
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if not math.isfinite(float(actual)):
            raise AssertionError(f"non-finite number at {path}")
        if not math.isclose(float(actual), float(expected), abs_tol=ATOL, rel_tol=RTOL):
            raise AssertionError(f"numeric mismatch outside 5e-4 tolerance at {path}")
        return
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"key mismatch at {path}")
        for key in expected:
            _compare(actual[key], expected[key], f"{path}.{key}")
        return
    if isinstance(expected, list) and isinstance(actual, list):
        if len(actual) != len(expected):
            raise AssertionError(f"length mismatch at {path}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            _compare(left, right, f"{path}[{index}]")
        return
    if actual != expected:
        raise AssertionError(f"value mismatch at {path}")


def _validate_scientific(actual: Any, expected: dict[str, Any]) -> None:
    if not isinstance(actual, dict) or set(actual) != SCIENTIFIC_KEYS:
        raise AssertionError("scientific result schema mismatch")
    _compare(actual, expected)
    if not 0.0 <= float(actual["DockQ"]) <= 1.0:
        raise AssertionError("DockQ is outside [0, 1]")


def _validate_standard_artifacts(observed: dict[str, Any]) -> None:
    if observed.get("caught") is not None:
        raise AssertionError(
            "AlphaFold host prediction unexpectedly raised an exception: "
            f"{observed['caught']}"
        )
    artifacts = observed.get("standard_artifacts")
    if not isinstance(artifacts, dict) or not all(artifacts.values()):
        raise AssertionError("pre-existing AlphaFold artifacts were not preserved")
    models = observed.get("model_outputs")
    if not isinstance(models, dict) or set(models) != {"model_alpha", "model_beta"}:
        raise AssertionError("AlphaFold did not preserve both model outputs")
    for item in models.values():
        if not item.get("result_exists") or not item.get("pdb_exists"):
            raise AssertionError("AlphaFold result pickle or PDB was lost")
        if not item.get("confidence_exists") or not item.get("unrelaxed_mmcif_exists"):
            raise AssertionError("AlphaFold confidence or mmCIF output was lost")
        if item.get("legacy_output") != [7, 11]:
            raise AssertionError("pre-existing prediction result content regressed")
    calls = observed.get("runner_calls", {})
    expected_calls = {
        "model_alpha": {"process_seeds": [6], "predict_seeds": [6]},
        "model_beta": {"process_seeds": [7], "predict_seeds": [7]},
    }
    if calls != expected_calls:
        raise AssertionError("model execution count or random seeds regressed")
    if len(observed.get("data_pipeline_calls", [])) != 1:
        raise AssertionError("AlphaFold data pipeline invocation regressed")
    ranking = observed.get("ranking")
    if not isinstance(ranking, dict) or ranking.get("order") != [
        "model_alpha", "model_beta"
    ]:
        raise AssertionError("AlphaFold confidence ranking regressed")
    timings = observed.get("timings")
    required_timings = {
        "features", "process_features_model_alpha", "process_features_model_beta",
        "predict_and_compile_model_alpha", "predict_and_compile_model_beta",
    }
    if not isinstance(timings, dict) or not required_timings.issubset(timings):
        raise AssertionError("AlphaFold timings output regressed")


def _validate_workflow_artifacts(observed: dict[str, Any], allow_error: bool) -> None:
    if not allow_error and observed.get("caught") is not None:
        raise AssertionError("workflow unexpectedly raised an exception")
    artifacts = observed.get("standard_artifacts")
    if not isinstance(artifacts, dict) or not all(artifacts.values()):
        raise AssertionError("workflow lost pre-existing AlphaFold artifacts")
    models = observed.get("model_outputs")
    if not isinstance(models, dict) or set(models) != {"model_alpha", "model_beta"}:
        raise AssertionError("workflow did not emit both prediction models")
    for item in models.values():
        if not item.get("result_exists") or not item.get("pdb_exists"):
            raise AssertionError("workflow lost a model pickle or PDB")
        if item.get("legacy_output") != [7, 11]:
            raise AssertionError("workflow changed legacy result content")
    if not observed.get("summary_exists"):
        raise AssertionError("dockq_scores.json was not produced")
    if observed.get("summary_nonstandard_json"):
        raise AssertionError("dockq_scores.json contains NaN or Infinity")
    summary = observed.get("summary")
    if not isinstance(summary, dict) or set(summary) != set(models):
        raise AssertionError("DockQ summary does not cover every model")
    for model_name, item in models.items():
        if item.get("dockq_evaluation") != summary.get(model_name):
            raise AssertionError("pickle DockQ record differs from summary JSON")


def _workflow_expected(reference: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "computed",
        "reason": None,
        "dockq": reference["DockQ"],
        "fnat": reference["fnat"],
        "irms": reference["iRMSD"],
        "lrms": reference["LRMSD"],
        "capri": reference["CAPRI"],
        "native_contacts": reference["native_contacts"],
        "preserved_contacts": reference["preserved_contacts"],
        "mapping": reference["mapping"],
    }


def _validate_empty_record(record: Any, status_name: str, reason: str) -> None:
    if not isinstance(record, dict) or set(record) != WORKFLOW_KEYS:
        raise AssertionError("DockQ workflow schema mismatch")
    if record["status"] != status_name or record["reason"] != reason:
        raise AssertionError("DockQ workflow status or reason mismatch")
    for key in WORKFLOW_KEYS - {"status", "reason"}:
        if record[key] is not None:
            raise AssertionError("non-computed DockQ record contains fabricated values")


def _case_payload(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "model": case["model"],
        "native": case["native"],
        "mapping": case["mapping"],
    }


def _record_case(
    case: dict[str, Any],
    passed: bool,
    detail: str,
    elapsed: float,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    return {
        "index": case["index"],
        "name": case["name"],
        "category": case["category"],
        "passed": bool(passed),
        "detail": detail[:1200],
        "elapsed_seconds": round(elapsed, 6),
        "reference_evidence": evidence,
    }


def _run_scored_case(
    case: dict[str, Any],
    cases: list[dict[str, Any]],
    references: list[dict[str, Any]],
    real_e2e_reference: dict[str, Any],
    real_e2e_cache: dict[str, Any],
) -> tuple[bool, str]:
    index = case["index"]
    if index <= 9:
        observed = _invoke_candidate("direct", _case_payload(case))
        if not observed.get("ok"):
            raise AssertionError(
                f"{observed.get('error_type', 'candidate error')}: "
                f"{observed.get('error', 'no diagnostic')}"
            )
        _validate_scientific(observed["value"], references[index - 1])
        return True, "locked DockQ differential passed"

    if index == 10:
        observed = _invoke_candidate("cli", _case_payload(case))
        if not observed.get("ok"):
            raise AssertionError(
                f"{observed.get('error_type', 'candidate error')}: "
                f"{observed.get('error', 'no diagnostic')}"
            )
        value = observed["value"]
        if value.get("returncode") != 0 or not value.get("output_exists"):
            raise AssertionError("standalone CLI failed or omitted its output")
        if value.get("nonstandard_json"):
            raise AssertionError("standalone CLI emitted NaN or Infinity")
        _validate_scientific(value.get("value"), references[index - 1])
        return True, "standalone JSON CLI differential passed"

    if index == 11:
        observed = _invoke_candidate("workflow_contract", {})
        if not observed.get("ok"):
            raise AssertionError(
                f"{observed.get('error_type', 'candidate error')}: "
                f"{observed.get('error', 'no diagnostic')}"
            )
        contract = observed["value"]
        if not isinstance(contract, dict) or not contract or not all(contract.values()):
            missing = sorted(key for key, value in (contract or {}).items() if not value)
            raise AssertionError(
                "AlphaFold DockQ CLI/signature contract incomplete"
                + (f": {', '.join(missing)}" if missing else "")
            )
        return True, "AlphaFold CLI flags, defaults, signature, and main pass-through passed"

    if "value" not in real_e2e_cache and "error" not in real_e2e_cache:
        try:
            real_e2e_cache["value"] = _run_real_e2e_candidate(real_e2e_reference)
        except Exception as exc:
            real_e2e_cache["error"] = f"{type(exc).__name__}: {exc}"
    if "error" in real_e2e_cache:
        raise AssertionError(real_e2e_cache["error"])
    real = real_e2e_cache["value"]
    metadata = real.get("metadata")
    observation = real.get("observation")
    if not isinstance(metadata, dict) or not isinstance(observation, dict):
        raise AssertionError("real E2E observation is malformed")

    if index == 12:
        devices = metadata.get("jax_devices")
        if not isinstance(devices, list) or not any(
            "cuda" in str(device).lower() or "gpu" in str(device).lower()
            for device in devices
        ):
            raise AssertionError(f"real E2E did not execute on a JAX GPU: {devices}")
        if metadata.get("data_pipeline_class") != (
            "alphafold.data.pipeline_multimer.DataPipeline"
        ):
            raise AssertionError("real E2E did not use official multimer DataPipeline")
        if metadata.get("model_runner_class") != "alphafold.model.model.RunModel":
            raise AssertionError("real E2E did not use official AlphaFold RunModel")
        if metadata.get("model_name") != "model_1_multimer_v3":
            raise AssertionError("real E2E did not use the locked multimer weights")
        if metadata.get("num_recycle") != 1 or metadata.get("integrated") is not True:
            raise AssertionError("real E2E model configuration or integration mode mismatch")
        return True, "real H200 DataPipeline + RunModel inference passed"

    if index == 13:
        if real.get("prediction_equivalent") is not True:
            raise AssertionError(
                "candidate changed the original AF2 unrelaxed prediction or confidence ranking"
            )
        return True, "pristine and modified AF2 predictions are byte-equivalent"

    if index == 14:
        summary = observation.get("summary")
        if not isinstance(summary, dict) or set(summary) != {REAL_E2E_MODEL_NAME}:
            raise AssertionError("real E2E dockq_scores.json has the wrong model set")
        record = summary[REAL_E2E_MODEL_NAME]
        if not isinstance(record, dict) or set(record) != WORKFLOW_KEYS:
            raise AssertionError("real E2E DockQ record schema mismatch")
        if record.get("status") != "computed" or record.get("reason") is not None:
            raise AssertionError("real E2E did not compute DockQ from the supplied native")
        actual = {
            "fnat": record["fnat"],
            "iRMSD": record["irms"],
            "LRMSD": record["lrms"],
            "DockQ": record["dockq"],
            "CAPRI": record["capri"],
            "native_contacts": record["native_contacts"],
            "preserved_contacts": record["preserved_contacts"],
            "mapping": record["mapping"],
        }
        _validate_scientific(actual, real_e2e_reference["dockq"])
        return True, "integrated in-memory DockQ matches locked original DockQ"

    artifacts = observation.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts or not all(artifacts.values()):
        missing = sorted(key for key, value in (artifacts or {}).items() if not value)
        raise AssertionError(f"real E2E output artifacts are incomplete: {missing}")
    summary = observation.get("summary")
    record = summary.get(REAL_E2E_MODEL_NAME) if isinstance(summary, dict) else None
    if observation.get("dockq_evaluation") != record:
        raise AssertionError("real result pickle and dockq_scores.json disagree")
    if observation.get("summary_nonstandard_json"):
        raise AssertionError("real dockq_scores.json contains NaN or Infinity")
    expected_keys = sorted(real_e2e_reference["result_keys"] + ["dockq_evaluation"])
    if observation.get("result_keys") != expected_keys:
        raise AssertionError("DockQ integration changed or dropped original AF2 result fields")
    return True, "real AF2 standard artifacts and integrated JSON/pickle passed"


def _write_reports(report: dict[str, Any], reward: float) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(LOG_DIR, 0o700)
    RESULTS_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    REWARD_PATH.write_text(f"{reward:.12g}\n", encoding="utf-8")
    os.chmod(RESULTS_PATH, 0o644)
    os.chmod(REWARD_PATH, 0o644)
    # Candidate processes have been reaped by this point.  Re-open the mounted
    # directory so Harbor's host process can collect files and write reward.json.
    os.chmod(LOG_DIR, 0o777)


def grade() -> tuple[dict[str, Any], float]:
    started = time.monotonic()
    cases = build_cases()
    references: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    hard_gates: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    isolation: dict[str, Any] = {}
    real_e2e_reference: dict[str, Any] = {}

    # Phase 1: locked references and the pristine real AF2 run happen before
    # candidate source is compiled/imported and before candidate uid runs at all.
    try:
        if not (REFERENCE_ROOT / "reference_runner.py").is_file():
            raise RuntimeError("locked reference runner is missing")
        donor_hashes = _donor_fingerprints()
        for case in cases:
            if case["index"] <= 10:
                expected, evidence = dockq_reference(case)
                references.append(expected)
                evidence_rows.append(evidence)
            else:
                references.append({})
                evidence_rows.append({"case_index": case["index"]})
        real_e2e_reference = _run_real_e2e_reference()
        for case_index in range(12, 16):
            evidence_rows[case_index - 1] = {
                "case_index": case_index,
                **real_e2e_reference["evidence"],
            }
        hard_gates.append(
            {
                "name": "locked_reference_generation",
                "passed": True,
                "hard_gate": False,
                "detail": (
                    "locked original DockQ executed dynamically; pristine locked AF2 "
                    "also ran a real H200 multimer inference"
                ),
            }
        )
    except Exception as exc:
        hard_gates.append(
            {
                "name": "locked_reference_generation",
                "passed": False,
                "hard_gate": False,
                "detail": f"verifier infrastructure failure: {type(exc).__name__}: {exc}"[:1200],
            }
        )
        try:
            if REFERENCE_ROOT.exists():
                shutil.rmtree(REFERENCE_ROOT)
        finally:
            for case in cases:
                case_rows.append(
                    _record_case(case, False, "not run: reference infrastructure failed", 0.0, {})
                )
        report = {
            "schema_version": 1,
            "donor_commit": DOCKQ_COMMIT,
            "tolerance": {"absolute": ATOL, "relative": RTOL},
            "hard_gate_passed": False,
            "hard_gates": hard_gates,
            "cases": case_rows,
            "passed_cases": 0,
            "total_cases": TOTAL_CASES,
            "reward": 0.0,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
        return report, 0.0

    # The runner is root-owned and contains inputs/test logic only.  Expected
    # answers remain solely in this root process's memory.
    _install_runner()
    isolation = _remove_reference_and_lock_tests()
    if not isolation["reference_removed"]:
        raise RuntimeError("failed to remove locked donor before candidate phase")

    gate_failed = False

    def run_hard_gate(name: str, callback) -> None:
        nonlocal gate_failed
        if gate_failed:
            hard_gates.append(
                {
                    "name": name,
                    "passed": False,
                    "hard_gate": True,
                    "detail": "skipped after an earlier hard-gate failure",
                }
            )
            return
        gate_started = time.monotonic()
        try:
            callback()
            hard_gates.append(
                {
                    "name": name,
                    "passed": True,
                    "hard_gate": True,
                    "detail": "passed",
                    "elapsed_seconds": round(time.monotonic() - gate_started, 6),
                }
            )
        except Exception as exc:
            gate_failed = True
            hard_gates.append(
                {
                    "name": name,
                    "passed": False,
                    "hard_gate": True,
                    "detail": f"{type(exc).__name__}: {exc}"[:1200],
                    "elapsed_seconds": round(time.monotonic() - gate_started, 6),
                }
            )

    run_hard_gate("compile", _compile_gate)
    run_hard_gate("locked_alphafold_tree_integrity", _host_tree_integrity_gate)
    run_hard_gate(
        "forbidden_dependency_or_vendored_donor",
        lambda: _forbidden_gate(donor_hashes),
    )

    def import_signature_gate() -> None:
        observed = _invoke_candidate("gate_import", {}, timeout=20)
        if not observed.get("ok"):
            raise AssertionError(
                f"{observed.get('error_type', 'candidate error')}: "
                f"{observed.get('error', 'no diagnostic')}"
            )

    run_hard_gate("unprivileged_import_and_score_complex_signature", import_signature_gate)

    def host_regression_gate() -> None:
        payload = {
            "models": [cases[0]["native"], cases[1]["model"]],
            "native_text": None,
        }
        observed = _invoke_candidate("host_regression", payload, timeout=35)
        if not observed.get("ok"):
            raise AssertionError(
                f"{observed.get('error_type', 'candidate error')}: "
                f"{observed.get('error', 'no diagnostic')}"
            )
        _validate_standard_artifacts(observed["value"])

    run_hard_gate("alphafold_host_regression_integrity", host_regression_gate)

    if gate_failed:
        for case, evidence in zip(cases, evidence_rows):
            case_rows.append(
                _record_case(
                    case,
                    False,
                    "not run: hard-gate failure makes reward zero",
                    0.0,
                    evidence,
                )
            )
        passed_count = 0
        reward = 0.0
    else:
        passed_count = 0
        real_e2e_cache: dict[str, Any] = {}
        for case, evidence in zip(cases, evidence_rows):
            case_started = time.monotonic()
            try:
                passed, detail = _run_scored_case(
                    case,
                    cases,
                    references,
                    real_e2e_reference,
                    real_e2e_cache,
                )
            except Exception as exc:
                passed = False
                detail = f"{type(exc).__name__}: {exc}"
            if passed:
                passed_count += 1
            case_rows.append(
                _record_case(
                    case,
                    passed,
                    detail,
                    time.monotonic() - case_started,
                    evidence,
                )
            )
        reward = passed_count / TOTAL_CASES

    report = {
        "schema_version": 1,
        "donor_commit": DOCKQ_COMMIT,
        "reference_policy": (
            "dynamic locked-original DockQ plus pristine real AF2/H200 completed "
            "before donor deletion; no expected values were written into /testbed"
        ),
        "tolerance": {"absolute": ATOL, "relative": RTOL},
        "isolation": isolation,
        "hard_gate_passed": not gate_failed,
        "hard_gates": hard_gates,
        "cases": case_rows,
        "passed_cases": passed_count,
        "total_cases": TOTAL_CASES,
        "reward": reward,
        "elapsed_seconds": round(time.monotonic() - started, 6),
    }
    return report, reward


def main() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(LOG_DIR, 0o700)
    try:
        report, reward = grade()
    except Exception as exc:
        try:
            if REFERENCE_ROOT.exists():
                shutil.rmtree(REFERENCE_ROOT)
            os.chmod("/tests", 0o700)
        except Exception:
            pass
        report = {
            "schema_version": 1,
            "donor_commit": DOCKQ_COMMIT,
            "hard_gate_passed": False,
            "hard_gates": [
                {
                    "name": "grader_integrity",
                    "passed": False,
                    "hard_gate": True,
                    "detail": f"{type(exc).__name__}: {exc}"[:1200],
                }
            ],
            "cases": [],
            "passed_cases": 0,
            "total_cases": TOTAL_CASES,
            "reward": 0.0,
        }
        reward = 0.0
    _write_reports(report, reward)
    print(
        f"DockQ integration grader: {report.get('passed_cases', 0)}/"
        f"{TOTAL_CASES}; reward={reward:.6f}; "
        f"hard_gates={'passed' if report.get('hard_gate_passed') else 'failed'}"
    )


if __name__ == "__main__":
    main()
