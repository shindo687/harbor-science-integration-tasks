#!/usr/bin/env python3
"""Isolated partial-credit grader for ColabFold + DockQ + ipSAE."""
from __future__ import annotations

import ast
import copy
import difflib
import hashlib
import io
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
import tokenize
from pathlib import Path
from typing import Any

import numpy as np
import Bio


TESTBED = Path("/testbed")
TARGET = TESTBED / "colabfold/alphafold/complex_metrics.py"
BATCH = TESTBED / "colabfold/batch.py"
TESTS = Path("/tests")
REFERENCE = TESTS / "reference"
LOG_DIR = Path("/logs/verifier")
RUNNER = Path("/opt/candidate-runner.py")
REWARD_PATH = LOG_DIR / "reward.txt"
RESULTS_PATH = LOG_DIR / "grader-results.json"
CANDIDATE_UID = 10001
CANDIDATE_GID = 10001
ATOL = 5e-4
RTOL = 5e-4
TOTAL_CASES = 15
MAX_NUMERIC_ABS_ERROR = 0.0
DOCKQ_COMMIT = "75db7ab4f6b824c70d120c5f620582e164ed5479"
IPSAE_COMMIT = "6174cf9e71cb1bd660cc805856a18c4871a6dec3"
HOST_COMMIT = "277662d7f4b0e4356c8d3fc4aec7c5a074cc65ad"
HOST_TREE = "3c473f8ce514a9d6836ae9381df26f1d6d3907d1"
DOCKQ_TREE = "1d067a65cc2ce796a355fb8982ac5885ef996dab"
IPSAE_TREE = "6c7e6e1c69d0150d7fd02d94593bd23387e9ebaa"
HOST_MANIFEST_SHA256 = "3a9eee87b25fc8d0a0a89455141417e2729324641e6cd99d27875e9a71912e14"
DOCKQ_MANIFEST_SHA256 = "2d8f1c162ba092d0cefb54e10723dff0938a3a6cf5b629186b66d0b6b598ac7e"
IPSAE_MANIFEST_SHA256 = "da113b9b241941ba45a69a5452fd9cb7414ea5814059961d5e09a84e7c0a8a08"
REFERENCE_MANIFEST_SHA256 = "a9ea4ea255cef9fc1716135f8ddd52525a83dc25063bdd8ca0c699cbc661e84f"
DOCKQ_KEYS = {
    "fnat", "iRMSD", "LRMSD", "DockQ", "CAPRI",
    "native_contacts", "preserved_contacts", "mapping",
}
IPSAE_TOP_KEYS = {"pae_cutoff", "distance_cutoff", "chain_pairs"}
IPSAE_PAIR_KEYS = {
    "chain1", "chain2", "type", "ipsae", "ipsae_d0chn", "ipsae_d0dom",
    "iptm_af", "iptm_d0chn", "pdockq", "pdockq2", "lis", "n0res",
    "n0chn", "n0dom", "d0res", "d0chn", "d0dom", "nres1", "nres2",
    "dist1", "dist2",
}
DOCKQ_STATE_KEYS = {
    "status", "reason", "dockq", "fnat", "irms", "lrms", "capri",
    "native_contacts", "preserved_contacts", "mapping",
}
IPSAE_STATE_KEYS = {
    "status", "reason", "pae_cutoff", "distance_cutoff", "chain_pairs",
}


def residue(name: str, center: tuple[float, float, float]) -> dict[str, Any]:
    x, y, z = center
    atoms = {
        "N": [x - 1.2, y, z],
        "CA": [x, y, z],
        "C": [x + 1.3, y, z],
        "O": [x + 1.8, y + 0.5, z],
    }
    if name != "GLY":
        atoms["CB"] = [x, y + 1.1, z + 0.7]
    return {"name": name, "atoms": atoms}


def chain(names: list[str], y: float, z: float = 0.0):
    return [residue(name, (index * 3.8, y, z)) for index, name in enumerate(names)]


def perturb(structure, chain_id: str, vector):
    result = copy.deepcopy(structure)
    delta = np.asarray(vector, dtype=float)
    for item in result["chains"][chain_id]:
        for atom_name, coord in item["atoms"].items():
            item["atoms"][atom_name] = (np.asarray(coord) + delta).tolist()
    return result


def transform(structure, rotation, translation):
    result = copy.deepcopy(structure)
    rotation = np.asarray(rotation, dtype=float)
    translation = np.asarray(translation, dtype=float)
    for residues in result["chains"].values():
        for item in residues:
            for atom_name, coord in item["atoms"].items():
                item["atoms"][atom_name] = (
                    np.asarray(coord) @ rotation + translation
                ).tolist()
    return result


def pdb_text(structure) -> str:
    lines = []
    serial = 1
    for chain_id, residues in structure["chains"].items():
        for residue_id, residue_data in enumerate(residues, 1):
            for atom_name, coord in residue_data["atoms"].items():
                x, y, z = coord
                shown = atom_name if len(atom_name) == 4 else f" {atom_name}"
                lines.append(
                    f"ATOM  {serial:5d} {shown:<4} {residue_data['name']:>3} "
                    f"{chain_id:1}{residue_id:4d}    {x:8.3f}{y:8.3f}{z:8.3f}"
                    f"{1.0:6.2f}{80.0:6.2f}          {atom_name[0]:>2}  "
                )
                serial += 1
        lines.append(
            f"TER   {serial:5d}      {residues[-1]['name']:>3} "
            f"{chain_id:1}{len(residues):4d}"
        )
        serial += 1
    lines.append("END")
    return "\n".join(line.ljust(80) for line in lines) + "\n"


def score_payload(structure, phase=0.0, high=False):
    chain_ids = []
    for chain_id, residues in structure["chains"].items():
        chain_ids.extend([chain_id] * len(residues))
    size = len(chain_ids)
    pae = np.zeros((size, size), dtype=float)
    for i in range(size):
        for j in range(size):
            if chain_ids[i] == chain_ids[j]:
                value = 1.1 + 0.05 * abs(i - j)
            elif high:
                value = 20.0 + ((i * 5 + j * 7) % 9)
            else:
                direction = 1.8 if chain_ids[i] > chain_ids[j] else 0.0
                value = 2.8 + direction + 0.21 * ((i * 7 + j * 3) % 37)
                value += phase * math.sin((i + 1) * (j + 2) * 0.09)
            pae[i, j] = max(0.25, value)
    return {
        "pae": np.around(pae, 5).tolist(),
        "plddt": [70.0 + ((index * 13 + int(phase * 11)) % 27) for index in range(size)],
        "iptm": round(0.58 + phase * 0.025, 5),
    }


def base_structures():
    names_a = [
        "ALA", "GLY", "SER", "LEU", "ASN", "THR", "VAL", "LYS", "ASP",
        "PHE", "GLU", "ILE", "ARG", "TYR", "MET", "PRO", "GLN", "CYS",
    ]
    names_b = [
        "TYR", "VAL", "ASP", "GLU", "ALA", "TRP", "SER", "HIS", "LEU",
        "GLY", "ASN", "LYS", "THR", "PHE",
    ]
    names_c = [
        "GLN", "PRO", "MET", "ARG", "ILE", "ASN", "CYS", "ALA", "TYR",
        "SER", "VAL", "GLU",
    ]
    dimer = {"chains": {"A": chain(names_a, 0.0), "B": chain(names_b, 4.15)}}
    trimer = {
        "chains": {
            "A": chain(names_a, 0.0),
            "B": chain(names_b, 4.15),
            "C": chain(names_c, -4.5, 0.7),
        }
    }
    single = {"chains": {"A": chain(names_a, 0.0)}}
    return dimer, trimer, single


def build_cases():
    dimer, trimer, single = base_structures()
    angle = 0.61
    rotation = [
        [math.cos(angle), -math.sin(angle), 0.0],
        [math.sin(angle), math.cos(angle), 0.0],
        [0.0, 0.0, 1.0],
    ]
    swapped = {
        "chains": {
            "X": copy.deepcopy(dimer["chains"]["B"]),
            "Y": copy.deepcopy(dimer["chains"]["A"]),
        }
    }
    return [
        {"name": "dockq_identity", "kind": "dockq", "model": dimer, "native": dimer},
        {"name": "dockq_ligand_shift", "kind": "dockq", "model": perturb(dimer, "B", [0.3, 1.25, -0.4]), "native": dimer},
        {"name": "dockq_rigid_distortion", "kind": "dockq", "model": transform(perturb(dimer, "B", [0.0, 2.3, 0.2]), rotation, [9.0, -4.0, 3.0]), "native": dimer},
        {"name": "dockq_sequence_chain_swap", "kind": "dockq", "model": swapped, "native": dimer},
        {"name": "dockq_explicit_mapping", "kind": "dockq", "model": perturb(dimer, "B", [-0.2, 1.7, 0.5]), "native": dimer, "mapping": {"A": "A", "B": "B"}},
        {"name": "ipsae_default_dimer", "kind": "ipsae", "model": dimer, "scores": score_payload(dimer, 0.2)},
        {"name": "ipsae_asymmetric_pae", "kind": "ipsae", "model": perturb(dimer, "B", [0.1, 0.9, 0.3]), "scores": score_payload(dimer, 0.9)},
        {"name": "ipsae_nondefault_cutoffs", "kind": "ipsae", "model": perturb(dimer, "B", [-0.4, 2.4, 0.2]), "scores": score_payload(dimer, 1.4), "pae_cutoff": 9.0, "distance_cutoff": 11.0},
        {"name": "ipsae_trimer_all_pairs", "kind": "ipsae", "model": trimer, "scores": score_payload(trimer, 0.7), "pae_cutoff": 13.0, "distance_cutoff": 14.0},
        {"name": "ipsae_no_pae_below_cutoff", "kind": "ipsae", "model": dimer, "scores": score_payload(dimer, 0.0, high=True), "pae_cutoff": 8.0, "distance_cutoff": 10.0},
        {"name": "combined_cli", "kind": "cli", "model": perturb(dimer, "B", [0.15, 1.55, -0.25]), "native": dimer, "scores": score_payload(dimer, 1.1), "pae_cutoff": 12.0, "distance_cutoff": 13.0},
        {"name": "public_contract_and_flags", "kind": "contract"},
        {"name": "workflow_computed_multimodel", "kind": "workflow_computed", "native": dimer, "models": [model_record("alpha", dimer, 0.91, score_payload(dimer, 0.3)), model_record("beta", perturb(dimer, "B", [0.2, 1.8, 0.4]), 0.79, score_payload(dimer, 0.8))]},
        {"name": "workflow_missing_and_disabled", "kind": "workflow_states", "native": dimer, "models": [model_record("state", dimer, 0.83, score_payload(dimer, 0.5))]},
        {"name": "workflow_directory_errors_and_applicability", "kind": "workflow_edge", "native": dimer, "single": single, "models": [model_record("edge", dimer, 0.81, score_payload(dimer, 1.0))]},
    ]


def model_record(name, structure, confidence, scores):
    return {
        "name": name,
        "structure": structure,
        "confidence": confidence,
        "pae": scores.get("pae"),
        "plddt": scores.get("plddt"),
        "iptm": scores.get("iptm", 0.61),
        "ptm": 0.66,
    }


def close(actual, expected, path="root"):
    global MAX_NUMERIC_ABS_ERROR
    if isinstance(actual, bool) or isinstance(expected, bool):
        if actual != expected:
            raise AssertionError(f"{path}: {actual!r} != {expected!r}")
    elif isinstance(actual, (int, float)) and isinstance(expected, (int, float)):
        MAX_NUMERIC_ABS_ERROR = max(
            MAX_NUMERIC_ABS_ERROR, abs(float(actual) - float(expected))
        )
        if not math.isclose(float(actual), float(expected), abs_tol=ATOL, rel_tol=RTOL):
            raise AssertionError(f"{path}: {actual} != {expected}")
    elif isinstance(actual, dict) and isinstance(expected, dict):
        if set(actual) != set(expected):
            raise AssertionError(f"{path}: key mismatch {set(actual) ^ set(expected)}")
        for key in expected:
            close(actual[key], expected[key], f"{path}.{key}")
    elif isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            raise AssertionError(f"{path}: length {len(actual)} != {len(expected)}")
        for index, (left, right) in enumerate(zip(actual, expected)):
            close(left, right, f"{path}[{index}]")
    elif actual != expected:
        raise AssertionError(f"{path}: {actual!r} != {expected!r}")


def dockq_reference(model, native, mapping=None, contact_cutoff=5.0, interface_cutoff=10.0):
    if contact_cutoff != 5.0 or interface_cutoff != 10.0:
        raise ValueError("the locked DockQ differential oracle uses its native 5A/10A cutoffs")
    with tempfile.TemporaryDirectory(prefix="dockq-reference-") as temp_name:
        temp = Path(temp_name)
        model_path = temp / "model.pdb"
        native_path = temp / "native.pdb"
        output = temp / "output.json"
        model_path.write_text(pdb_text(model), encoding="utf-8")
        native_path.write_text(pdb_text(native), encoding="utf-8")
        command = [
            sys.executable,
            str(REFERENCE / "dockq_reference_runner.py"),
            str(model_path),
            str(native_path),
            str(output),
        ]
        if mapping:
            model_ids = sorted(mapping)
            command.append(
                "".join(model_ids) + ":" + "".join(mapping[key] for key in model_ids)
            )
        env = {
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": f"{REFERENCE / 'shims'}:{REFERENCE / 'dockq/src'}",
            "HOME": temp_name,
            "TMPDIR": temp_name,
        }
        completed = subprocess.run(command, env=env, text=True, capture_output=True)
        if completed.returncode:
            raise RuntimeError(f"locked DockQ failed: {completed.stderr}\n{completed.stdout}")
        return json.loads(output.read_text(encoding="utf-8"))


def ipsae_reference(model, scores, pae_cutoff=15.0, distance_cutoff=15.0):
    with tempfile.TemporaryDirectory(prefix="ipsae-reference-") as temp_name:
        temp = Path(temp_name)
        model_path = temp / "model.pdb"
        scores_path = temp / "scores.json"
        output = temp / "output.json"
        model_path.write_text(pdb_text(model), encoding="utf-8")
        scores_path.write_text(json.dumps(scores, allow_nan=False), encoding="utf-8")
        completed = subprocess.run(
            [
                sys.executable,
                str(REFERENCE / "ipsae_reference_runner.py"),
                str(REFERENCE / "ipsae/ipsae.py"),
                str(scores_path),
                str(model_path),
                str(output),
                str(pae_cutoff),
                str(distance_cutoff),
            ],
            text=True,
            capture_output=True,
        )
        if completed.returncode:
            raise RuntimeError(f"locked ipSAE failed: {completed.stderr}\n{completed.stdout}")
        return json.loads(output.read_text(encoding="utf-8"))


def build_references(cases):
    references = {}
    evidence = []
    for case in cases:
        name = case["name"]
        if case["kind"] == "dockq":
            references[name] = dockq_reference(
                case["model"], case["native"], case.get("mapping")
            )
            evidence.append({"case": name, "donor": "DockQ"})
        elif case["kind"] == "ipsae":
            references[name] = ipsae_reference(
                case["model"], case["scores"], case.get("pae_cutoff", 15.0),
                case.get("distance_cutoff", 15.0),
            )
            evidence.append({"case": name, "donor": "IPSAE"})
        elif case["kind"] == "cli":
            references[name] = {
                "dockq": dockq_reference(case["model"], case["native"]),
                "ipsae": ipsae_reference(
                    case["model"], case["scores"], case["pae_cutoff"],
                    case["distance_cutoff"],
                ),
            }
            evidence.extend(({"case": name, "donor": "DockQ"}, {"case": name, "donor": "IPSAE"}))
        elif case["kind"] == "workflow_computed":
            refs = []
            for model in case["models"]:
                score_data = {
                    "pae": model["pae"], "plddt": model["plddt"], "iptm": model["iptm"]
                }
                refs.append({
                    "dockq": dockq_reference(model["structure"], case["native"]),
                    "ipsae": ipsae_reference(model["structure"], score_data),
                })
            references[name] = refs
            evidence.append({"case": name, "donor": "both", "runs": len(refs)})
        elif case["kind"] == "workflow_edge":
            model = case["models"][0]
            score_data = {"pae": model["pae"], "plddt": model["plddt"], "iptm": model["iptm"]}
            references[name] = {
                "dockq": dockq_reference(model["structure"], case["native"]),
                "ipsae": ipsae_reference(model["structure"], score_data),
            }
            evidence.append({"case": name, "donor": "both"})
    return references, evidence


def invoke(mode, payload, timeout=40):
    candidate_home = Path("/tmp/candidate-home")
    candidate_home.mkdir(exist_ok=True)
    os.chown(candidate_home, CANDIDATE_UID, CANDIDATE_GID)
    env = {
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(TESTBED),
        "PYTHONNOUSERSITE": "1",
        "HOME": "/tmp/candidate-home",
        "TMPDIR": "/tmp",
        "OPENBLAS_NUM_THREADS": "1",
        "OMP_NUM_THREADS": "1",
    }
    def demote():
        os.setgroups([])
        os.setgid(CANDIDATE_GID)
        os.setuid(CANDIDATE_UID)

    command = [sys.executable, str(RUNNER), mode]
    completed = subprocess.run(
        command,
        input=json.dumps(payload, allow_nan=False),
        text=True,
        capture_output=True,
        env=env,
        cwd=str(candidate_home),
        preexec_fn=demote if os.getuid() == 0 else None,
        timeout=timeout,
    )
    if completed.stderr.strip():
        raise AssertionError(f"candidate emitted stderr: {completed.stderr[-1600:]}")
    if completed.returncode:
        raise AssertionError(
            f"candidate runner exited {completed.returncode}: {completed.stderr}"
        )
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    if not lines:
        raise AssertionError("candidate runner returned no JSON")
    observed = json.loads(lines[-1])
    if not observed.get("ok"):
        raise AssertionError(
            f"{observed.get('error_type')}: {observed.get('error')}"
        )
    return observed["value"]


def compile_gate():
    if not TARGET.exists():
        raise AssertionError(f"missing {TARGET}")
    subprocess.run(
        [sys.executable, "-m", "py_compile", str(TARGET), str(BATCH)],
        check=True,
        env={"PATH": "/usr/bin:/bin", "PYTHONPYCACHEPREFIX": "/tmp/grader-pyc"},
    )


def python_tokens(path):
    tokens = []
    with path.open(encoding="utf-8") as handle:
        stream = tokenize.generate_tokens(handle.readline)
        for token in stream:
            if token.type not in {
                tokenize.ENCODING, tokenize.ENDMARKER, tokenize.INDENT,
                tokenize.DEDENT, tokenize.NEWLINE, tokenize.NL, tokenize.COMMENT,
            }:
                tokens.append(token.string)
    return tokens


def dependency_gate(donor_hashes, donor_token_streams):
    forbidden = {
        "dockq", "ipsae", "subprocess", "requests", "urllib", "socket",
        "ctypes", "http", "ftplib", "paramiko",
    }
    for candidate_path in (TARGET, BATCH):
        tree = ast.parse(candidate_path.read_text(encoding="utf-8"), filename=str(candidate_path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = {alias.name.split(".", 1)[0].lower() for alias in node.names}
                bad = roots & forbidden
                if bad:
                    raise AssertionError(
                        f"forbidden import in {candidate_path.name}: {sorted(bad)}"
                    )
            elif isinstance(node, ast.ImportFrom) and node.module:
                root = node.module.split(".", 1)[0].lower()
                if root in forbidden:
                    raise AssertionError(
                        f"forbidden import in {candidate_path.name}: {root}"
                    )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id in {"exec", "eval", "compile", "__import__"}:
                    raise AssertionError(
                        f"forbidden dynamic execution in {candidate_path.name}: {node.func.id}"
                    )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in {"system", "popen", "spawn", "execv", "execve"}:
                    raise AssertionError(
                        f"forbidden runtime call in {candidate_path.name}: {node.func.attr}"
                    )
        candidate_tokens = python_tokens(candidate_path)
        for donor_name, donor_tokens in donor_token_streams:
            if min(len(candidate_tokens), len(donor_tokens)) < 200:
                continue
            matcher = difflib.SequenceMatcher(
                None, candidate_tokens, donor_tokens, autojunk=False
            )
            similarity = matcher.ratio()
            matching_blocks = matcher.get_matching_blocks()
            largest_block = max(block.size for block in matching_blocks)
            matched_tokens = sum(block.size for block in matching_blocks)
            donor_coverage = matched_tokens / len(donor_tokens)
            if (
                similarity >= 0.30
                or largest_block >= 80
                or donor_coverage >= 0.60
            ):
                raise AssertionError(
                    f"candidate source resembles vendored {donor_name}: "
                    f"similarity={similarity:.3f}, largest_block={largest_block}, "
                    f"donor_coverage={donor_coverage:.3f}"
                )
    for path in TESTBED.rglob("*"):
        if not path.is_file() or path.suffix == ".pyc":
            continue
        if path.stat().st_size > 2_000_000:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest in donor_hashes:
            raise AssertionError(f"vendored donor file detected: {path.relative_to(TESTBED)}")


def batch_structure_gate():
    lock = json.loads((TESTS / "batch-structure-lock.json").read_text())
    expected = lock["preserved_top_level_ast_sha256"]
    observed = {}
    tree = ast.parse(BATCH.read_text(encoding="utf-8"), filename=str(BATCH))
    mutable = {
        "predict_structure", "run", "main", "_dockq_state", "_ipsae_state",
        "_native_for_job",
    }
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in mutable:
                continue
            key = f"{type(node).__name__}:{node.name}"
            digest = hashlib.sha256(
                ast.dump(node, annotate_fields=True, include_attributes=False).encode()
            ).hexdigest()
            observed[key] = digest
    if observed != expected:
        changed = sorted(
            key for key in set(observed) | set(expected)
            if observed.get(key) != expected.get(key)
        )
        raise AssertionError(
            f"unrelated top-level batch definitions changed: {changed[:12]}"
        )
    excluded_functions = {
        "predict_structure", "run", "main", "_dockq_state", "_ipsae_state",
        "_native_for_job",
    }
    preserved_nodes = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in excluded_functions:
                continue
        # The task requires adding BooleanOptionalAction to this one existing
        # import; every other module-level import/assignment/class stays locked.
        if isinstance(node, ast.ImportFrom) and node.module == "argparse":
            continue
        preserved_nodes.append(node)
    preserved_module = ast.Module(body=preserved_nodes, type_ignores=[])
    module_digest = hashlib.sha256(
        ast.dump(
            preserved_module, annotate_fields=True, include_attributes=False
        ).encode()
    ).hexdigest()
    if module_digest != lock["preserved_module_ast_sha256"]:
        raise AssertionError("unrelated batch module-level code changed")


def lock_candidate_tree():
    subprocess.run(["chown", "-R", "root:root", str(TESTBED)], check=True)
    subprocess.run(["chmod", "-R", "a-w", str(TESTBED)], check=True)


def integrity_gate():
    expected = {}
    for line in (TESTS / "host-files.sha256").read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, relative = line.split(None, 1)
            expected[relative.strip()] = digest
    for relative, digest in expected.items():
        path = TESTBED / relative
        if not path.exists():
            raise AssertionError(f"locked host file missing: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != digest:
            raise AssertionError(f"locked host file changed: {relative}")
    allowed = set(expected) | {"colabfold/batch.py", "colabfold/alphafold/complex_metrics.py"}
    actual_files = {
        str(path.relative_to(TESTBED))
        for path in TESTBED.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
    }
    extras = actual_files - allowed
    if extras:
        raise AssertionError(f"unexpected files in candidate tree: {sorted(extras)[:12]}")


def reference_integrity_gate(provenance):
    if sys.version_info[:3] != (3, 12, 11):
        raise AssertionError(f"unexpected Python runtime: {sys.version.split()[0]}")
    if np.__version__ != "2.2.6" or Bio.__version__ != "1.85":
        raise AssertionError(
            f"unexpected scientific runtime: numpy={np.__version__}, "
            f"biopython={Bio.__version__}"
        )
    expected_identity = {
        "host.commit": HOST_COMMIT,
        "host.tree": HOST_TREE,
        "host.snapshot_manifest_sha256": HOST_MANIFEST_SHA256,
        "dockq.commit": DOCKQ_COMMIT,
        "dockq.tree": DOCKQ_TREE,
        "dockq.snapshot_manifest_sha256": DOCKQ_MANIFEST_SHA256,
        "ipsae.commit": IPSAE_COMMIT,
        "ipsae.tree": IPSAE_TREE,
        "ipsae.snapshot_manifest_sha256": IPSAE_MANIFEST_SHA256,
        "reference_snapshot_manifest_sha256": REFERENCE_MANIFEST_SHA256,
    }
    for dotted, expected in expected_identity.items():
        value = provenance
        for key in dotted.split("."):
            value = value.get(key) if isinstance(value, dict) else None
        if value != expected:
            raise AssertionError(f"reference identity mismatch: {dotted}")

    manifest_path = TESTS / "reference-files.sha256"
    if hashlib.sha256(manifest_path.read_bytes()).hexdigest() != REFERENCE_MANIFEST_SHA256:
        raise AssertionError("reference manifest identity mismatch")
    expected_files = {}
    for line in manifest_path.read_text().splitlines():
        digest, relative = line.split(None, 1)
        expected_files[relative.strip()] = digest
    actual_files = {
        str(path.relative_to(REFERENCE)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in REFERENCE.rglob("*") if path.is_file()
    }
    if actual_files != expected_files:
        raise AssertionError("reference snapshot file hashes mismatch")

    host_manifest = TESTS / "host-snapshot.sha256"
    if hashlib.sha256(host_manifest.read_bytes()).hexdigest() != HOST_MANIFEST_SHA256:
        raise AssertionError("host snapshot manifest identity mismatch")
    for line in host_manifest.read_text().splitlines():
        digest, relative = line.split(None, 1)
        path = TESTBED / relative.strip()
        if relative.strip() == "colabfold/batch.py":
            continue
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise AssertionError(f"host snapshot identity mismatch: {relative.strip()}")


def check_contract(value):
    if value["score_dockq"] != [
        "model_pdb", "native_pdb", "mapping", "contact_cutoff", "interface_cutoff"
    ]:
        raise AssertionError(f"score_dockq signature mismatch: {value['score_dockq']}")
    if value["score_ipsae"] != [
        "pae", "plddt", "model_pdb", "pae_cutoff", "distance_cutoff", "iptm"
    ]:
        raise AssertionError(f"score_ipsae signature mismatch: {value['score_ipsae']}")
    required = [
        "run_dockq", "dockq_native_path", "run_ipsae",
        "ipsae_pae_cutoff", "ipsae_distance_cutoff",
    ]
    for function in ("predict_structure", "run"):
        args = value["batch_signatures"].get(function, [])
        if args[-5:] != required:
            raise AssertionError(f"{function} tail parameters mismatch: {args[-5:]}")
    if not all(value["flags"].values()):
        raise AssertionError(f"missing CLI flags: {value['flags']}")


def contract_case():
    check_contract(invoke("contract", {}))


def dockq_state(reference):
    return {
        "status": "computed", "reason": None,
        "dockq": reference["DockQ"], "fnat": reference["fnat"],
        "irms": reference["iRMSD"], "lrms": reference["LRMSD"],
        "capri": reference["CAPRI"],
        "native_contacts": reference["native_contacts"],
        "preserved_contacts": reference["preserved_contacts"],
        "mapping": reference["mapping"],
    }


def ipsae_state(reference):
    return {
        "status": "computed", "reason": None,
        "pae_cutoff": reference["pae_cutoff"],
        "distance_cutoff": reference["distance_cutoff"],
        "chain_pairs": reference["chain_pairs"],
    }


def check_workflow(value, expected_by_rank, count):
    if value["summary"] is None:
        raise AssertionError("complex metrics summary was not generated")
    close(value["summary"], expected_by_rank, "summary")
    close(value["returned_complex_metrics"], expected_by_rank, "return.complex_metrics")
    if len(value["scores"]) != count or len(value["pdb_names"]) != count:
        raise AssertionError("original scores/PDB artifacts were not preserved")
    if not value["all_result_files_exist"]:
        raise AssertionError("predict_structure returned missing result files")
    for filename, scores in value["scores"].items():
        rank = filename.split("_scores_", 1)[1].rsplit(".json", 1)[0]
        if "plddt" not in scores:
            raise AssertionError("pre-existing pLDDT output was lost")
        close(scores.get("complex_metrics"), expected_by_rank[rank], filename)


def run_case(case, references):
    kind = case["kind"]
    if kind == "dockq":
        actual = invoke("dockq", case)
        if set(actual) != DOCKQ_KEYS:
            raise AssertionError(f"DockQ schema mismatch: {set(actual) ^ DOCKQ_KEYS}")
        close(actual, references[case["name"]])
    elif kind == "ipsae":
        actual = invoke("ipsae", case)
        if set(actual) != IPSAE_TOP_KEYS:
            raise AssertionError(f"ipSAE top schema mismatch: {set(actual) ^ IPSAE_TOP_KEYS}")
        if any(set(record) != IPSAE_PAIR_KEYS for record in actual["chain_pairs"]):
            raise AssertionError("ipSAE chain-pair schema mismatch")
        close(actual, references[case["name"]])
    elif kind == "cli":
        actual = invoke("cli", case)
        if not actual["standard_json"]:
            raise AssertionError("CLI output is not standard JSON")
        close(actual["value"], references[case["name"]])
    elif kind == "contract":
        contract_case()
    elif kind == "workflow_computed":
        value = invoke(
            "workflow",
            {**case, "native_mode": "valid", "run_dockq": True, "run_ipsae": True},
            timeout=60,
        )
        ordered = sorted(
            zip(case["models"], references[case["name"]]),
            key=lambda item: item[0]["confidence"],
            reverse=True,
        )
        expected = {}
        for index, (model, ref) in enumerate(ordered, 1):
            rank = f"rank_{index:03d}_alphafold2_multimer_v3_{model['name']}_seed_007"
            expected[rank] = {
                "schema_version": 1,
                "dockq": dockq_state(ref["dockq"]),
                "ipsae": ipsae_state(ref["ipsae"]),
            }
        check_workflow(value, expected, len(case["models"]))
    elif kind == "workflow_states":
        missing = invoke("workflow", {**case, "native_mode": "missing"})
        rank = next(iter(missing["summary"]))
        record = missing["summary"][rank]
        if set(record["dockq"]) != DOCKQ_STATE_KEYS or set(record["ipsae"]) != IPSAE_STATE_KEYS:
            raise AssertionError("workflow state schema mismatch")
        if record["dockq"]["status"] != "not_computed" or record["dockq"]["reason"] != "native_structure_not_provided":
            raise AssertionError(f"unexpected missing-native state: {record['dockq']}")
        disabled = invoke(
            "workflow",
            {**case, "native_mode": "invalid", "run_dockq": False, "run_ipsae": False},
        )
        disabled_record = next(iter(disabled["summary"].values()))
        if disabled_record["dockq"]["status"] != "disabled" or disabled_record["ipsae"]["status"] != "disabled":
            raise AssertionError(f"disabled state mismatch: {disabled_record}")
    elif kind == "workflow_edge":
        directory = invoke("workflow", {**case, "native_mode": "directory_valid"})
        rank = next(iter(directory["summary"]))
        expected_ref = references[case["name"]]
        close(
            directory["summary"][rank],
            {"schema_version": 1, "dockq": dockq_state(expected_ref["dockq"]), "ipsae": ipsae_state(expected_ref["ipsae"])},
        )
        invalid = invoke("workflow", {**case, "native_mode": "invalid"})
        invalid_record = next(iter(invalid["summary"].values()))
        if invalid_record["dockq"]["status"] != "error" or not invalid_record["dockq"]["reason"]:
            raise AssertionError("invalid native did not produce a diagnostic error state")
        no_pae_models = copy.deepcopy(case["models"])
        no_pae_models[0]["pae"] = None
        no_pae = invoke("workflow", {**case, "models": no_pae_models, "native_mode": "missing"})
        if next(iter(no_pae["summary"].values()))["ipsae"]["status"] != "not_computed":
            raise AssertionError("missing PAE state mismatch")
        single_scores = score_payload(case["single"], 0.2)
        single_model = model_record("single", case["single"], 0.8, single_scores)
        single = invoke(
            "workflow",
            {**case, "models": [single_model], "is_complex": False, "native_mode": "missing"},
        )
        single_record = next(iter(single["summary"].values()))
        if single_record["ipsae"]["status"] != "not_applicable":
            raise AssertionError("single-chain ipSAE state mismatch")
    else:
        raise AssertionError(f"unknown case kind: {kind}")


def hard_gate(name, callback, rows):
    started = time.monotonic()
    try:
        callback()
        rows.append({"name": name, "passed": True, "detail": "passed", "elapsed_seconds": round(time.monotonic() - started, 6)})
        return True
    except Exception as exc:
        rows.append({"name": name, "passed": False, "detail": f"{type(exc).__name__}: {exc}"[:1600], "elapsed_seconds": round(time.monotonic() - started, 6)})
        return False


def main():
    started = time.monotonic()
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(LOG_DIR, 0o700)
    cases = build_cases()
    hard_gates = []
    case_rows = []
    reward = 0.0
    references = {}
    evidence = []
    donor_hashes = set()
    donor_token_streams = []
    try:
        donor_code_roots = (
            REFERENCE / "dockq/src/DockQ",
            REFERENCE / "ipsae",
        )
        for root in donor_code_roots:
            for path in root.rglob("*.py"):
                # Ignore empty package markers and tiny generic wrappers; the
                # gate is for copied donor implementations, not boilerplate.
                if path.is_file() and path.stat().st_size >= 1000:
                    donor_hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
                    donor_token_streams.append(
                        (str(path.relative_to(REFERENCE)), python_tokens(path))
                    )
        provenance = json.loads((TESTS / "reference-provenance.json").read_text(encoding="utf-8"))
        reference_integrity_gate(provenance)
        references, evidence = build_references(cases)

        shutil.copyfile(TESTS / "candidate_runner.py", RUNNER)
        os.chown(RUNNER, 0, 0)
        os.chmod(RUNNER, 0o755)
        shutil.rmtree(REFERENCE)
        os.chmod(TESTS, 0o700)
        if REFERENCE.exists():
            raise AssertionError("reference trees remain before candidate execution")
        lock_candidate_tree()

        gates_ok = hard_gate("compile", compile_gate, hard_gates)
        if gates_ok:
            def import_and_isolation_gate():
                value = invoke("gate_import", {})
                check_contract(value["contract"])
                if not all(value["isolation"].values()):
                    raise AssertionError(
                        f"candidate isolation mismatch: {value['isolation']}"
                    )
            gates_ok = hard_gate(
                "unprivileged_import_and_signatures",
                import_and_isolation_gate,
                hard_gates,
            )
        if gates_ok:
            gates_ok = hard_gate(
                "forbidden_dependency_or_vendored_donor",
                lambda: dependency_gate(donor_hashes, donor_token_streams),
                hard_gates,
            )
        if gates_ok:
            gates_ok = hard_gate("locked_host_integrity", integrity_gate, hard_gates)
        if gates_ok:
            gates_ok = hard_gate(
                "preserved_batch_structure", batch_structure_gate, hard_gates
            )
        if gates_ok:
            dimer, _, _ = base_structures()
            regression_model = model_record("regression", dimer, 0.8, score_payload(dimer, 0.1))
            def regression():
                value = invoke(
                    "workflow",
                    {"models": [regression_model], "native_mode": "missing", "run_ipsae": False},
                )
                if len(value["scores"]) != 1 or len(value["pdb_names"]) != 1:
                    raise AssertionError("standard ColabFold artifacts regressed")
                if not value["all_result_files_exist"]:
                    raise AssertionError("returned result files are missing")
            gates_ok = hard_gate("colabfold_standard_artifact_regression", regression, hard_gates)

        passed = 0
        if gates_ok:
            for case in cases:
                case_started = time.monotonic()
                try:
                    run_case(case, references)
                    passed += 1
                    case_rows.append({"name": case["name"], "passed": True, "detail": "passed", "elapsed_seconds": round(time.monotonic() - case_started, 6)})
                except Exception as exc:
                    case_rows.append({"name": case["name"], "passed": False, "detail": f"{type(exc).__name__}: {exc}"[:1800], "elapsed_seconds": round(time.monotonic() - case_started, 6)})
            reward = passed / TOTAL_CASES
        else:
            for case in cases:
                case_rows.append({"name": case["name"], "passed": False, "detail": "not run: hard-gate failure"})

        report = {
            "schema_version": 1,
            "donor_commits": {"dockq": DOCKQ_COMMIT, "ipsae": IPSAE_COMMIT},
            "locked_identity": {
                "host_commit": HOST_COMMIT,
                "host_tree": HOST_TREE,
                "dockq_commit": DOCKQ_COMMIT,
                "dockq_tree": DOCKQ_TREE,
                "ipsae_commit": IPSAE_COMMIT,
                "ipsae_tree": IPSAE_TREE,
                "host_manifest_sha256": HOST_MANIFEST_SHA256,
                "reference_manifest_sha256": REFERENCE_MANIFEST_SHA256,
            },
            "reference_policy": "locked originals run before physical donor deletion; candidate runs as uid 10001",
            "reference_evidence": evidence,
            "tolerance": {"absolute": ATOL, "relative": RTOL},
            "runtime": {
                "python": sys.version.split()[0],
                "numpy": np.__version__,
                "biopython": Bio.__version__,
            },
            "hard_gate_passed": gates_ok,
            "hard_gates": hard_gates,
            "cases": case_rows,
            "passed_cases": passed if gates_ok else 0,
            "total_cases": TOTAL_CASES,
            "reward": reward,
            "max_numeric_abs_error": MAX_NUMERIC_ABS_ERROR,
            "elapsed_seconds": round(time.monotonic() - started, 6),
        }
    except Exception as exc:
        if REFERENCE.exists():
            shutil.rmtree(REFERENCE)
        report = {
            "schema_version": 1,
            "donor_commits": {"dockq": DOCKQ_COMMIT, "ipsae": IPSAE_COMMIT},
            "hard_gate_passed": False,
            "hard_gates": [{"name": "grader_integrity", "passed": False, "detail": f"{type(exc).__name__}: {exc}"[:1800]}],
            "cases": [],
            "passed_cases": 0,
            "total_cases": TOTAL_CASES,
            "reward": 0.0,
        }
        reward = 0.0

    RESULTS_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REWARD_PATH.write_text(f"{reward:.12g}\n", encoding="utf-8")
    print(
        f"ColabFold DockQ+ipSAE grader: {report.get('passed_cases', 0)}/{TOTAL_CASES}; "
        f"reward={reward:.6f}; hard_gates={'passed' if report.get('hard_gate_passed') else 'failed'}"
    )


if __name__ == "__main__":
    main()
