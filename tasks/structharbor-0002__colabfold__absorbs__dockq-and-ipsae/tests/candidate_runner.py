#!/usr/bin/env python3
"""Unprivileged candidate harness; contains inputs and checks, never references."""
from __future__ import annotations

import ast
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
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import numpy as np


TESTBED = Path("/testbed")
TARGET = TESTBED / "colabfold/alphafold/complex_metrics.py"
BATCH = TESTBED / "colabfold/batch.py"


def load_candidate():
    spec = importlib.util.spec_from_file_location("candidate_complex_metrics", TARGET)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {TARGET}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pdb_text(structure: dict[str, Any]) -> str:
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


class FakeProtein:
    def __init__(self, structure):
        self.structure = structure


class ProteinApi:
    @staticmethod
    def from_prediction(features, result, b_factors, remove_leading_feature_dimension):
        del features, b_factors, remove_leading_feature_dimension
        return FakeProtein(result["_fixture_structure"])

    @staticmethod
    def to_pdb(protein):
        return pdb_text(protein.structure)


class FakeRunner:
    def __init__(self, model):
        self.model = model
        self.params = None

    def predict(self, input_features, random_seed, return_representations, callback):
        del input_features, random_seed, return_representations, callback
        size = sum(len(chain) for chain in self.model["structure"]["chains"].values())
        result = {
            "ranking_confidence": float(self.model.get("confidence", 0.7)),
            "plddt": np.asarray(self.model.get("plddt", [80.0] * size), dtype=float),
            "ptm": float(self.model.get("ptm", 0.66)),
            "iptm": float(self.model.get("iptm", 0.61)),
            "structure_module": {"final_atom_mask": np.ones((size, 5), dtype=float)},
            "_fixture_structure": self.model["structure"],
        }
        if self.model.get("pae") is not None:
            result["predicted_aligned_error"] = np.asarray(self.model["pae"], dtype=float)
        return result, 3


def load_predict_structure():
    tree = ast.parse(BATCH.read_text(encoding="utf-8"), filename=str(BATCH))
    wanted_functions = {
        "_dockq_state",
        "_ipsae_state",
        "_native_for_job",
        "predict_structure",
    }
    selected = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "file_manager":
            selected.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted_functions:
            selected.append(node)
    found = {
        node.name
        for node in selected
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = (wanted_functions | {"file_manager"}) - found
    if missing:
        raise AssertionError(f"workflow definitions missing: {sorted(missing)}")

    namespace = {
        "Any": Any,
        "Callable": Callable,
        "Dict": Dict,
        "List": List,
        "Optional": Optional,
        "Tuple": Tuple,
        "Union": Union,
        "Path": Path,
        "model": types.SimpleNamespace(RunModel=object),
        "haiku": types.SimpleNamespace(Params=object),
        "np": np,
        "json": json,
        "pickle": pickle,
        "time": time,
        "protein": ProteinApi,
        "logger": types.SimpleNamespace(info=lambda *_args, **_kwargs: None),
        "extra_ptm": types.SimpleNamespace(),
        "relax_me": lambda pdb_lines, **_kwargs: pdb_lines,
        "hasOrjson": False,
    }
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(module, str(BATCH), "exec"), namespace)
    return namespace["predict_structure"]


def workflow(payload):
    predict_structure = load_predict_structure()
    prefix = payload.get("prefix", "fixture")
    models = payload["models"]
    is_complex = bool(payload.get("is_complex", True))
    run_dockq = bool(payload.get("run_dockq", True))
    run_ipsae = bool(payload.get("run_ipsae", True))
    pae_cutoff = float(payload.get("pae_cutoff", 15.0))
    distance_cutoff = float(payload.get("distance_cutoff", 15.0))
    native_mode = payload.get("native_mode", "missing")

    with tempfile.TemporaryDirectory(prefix="candidate-workflow-") as temp_name:
        result_dir = Path(temp_name) / "results"
        result_dir.mkdir()
        native_argument = None
        if native_mode == "valid":
            native_argument = Path(temp_name) / "native.pdb"
            native_argument.write_text(pdb_text(payload["native"]), encoding="utf-8")
        elif native_mode == "directory_valid":
            native_argument = Path(temp_name) / "natives"
            native_argument.mkdir()
            (native_argument / f"{prefix}.pdb").write_text(
                pdb_text(payload["native"]), encoding="utf-8"
            )
        elif native_mode == "invalid":
            native_argument = Path(temp_name) / "invalid.pdb"
            native_argument.write_text("not a PDB\n", encoding="utf-8")

        runner_params = [
            (model["name"], FakeRunner(model), {"fixture": index})
            for index, model in enumerate(models)
        ]
        size = sum(len(chain) for chain in models[0]["structure"]["chains"].values())
        feature_dict = {"asym_id": np.zeros((1, size), dtype=int)}
        returned = predict_structure(
            prefix=prefix,
            result_dir=result_dir,
            feature_dict=feature_dict,
            is_complex=is_complex,
            use_templates=False,
            sequences_lengths=[len(chain) for chain in models[0]["structure"]["chains"].values()],
            pad_len=size,
            model_type="alphafold2_multimer_v3",
            model_runner_and_params=runner_params,
            num_relax=0,
            random_seed=7,
            num_seeds=1,
            rank_by="auto",
            run_dockq=run_dockq,
            dockq_native_path=native_argument,
            run_ipsae=run_ipsae,
            ipsae_pae_cutoff=pae_cutoff,
            ipsae_distance_cutoff=distance_cutoff,
        )

        summary_path = result_dir / f"{prefix}_complex_metrics.json"
        summary = (
            json.loads(summary_path.read_text(encoding="utf-8"))
            if summary_path.exists()
            else None
        )
        score_payloads = {}
        for score_path in sorted(result_dir.glob(f"{prefix}_scores_rank_*.json")):
            score_payloads[score_path.name] = json.loads(score_path.read_text(encoding="utf-8"))
        pdb_names = sorted(path.name for path in result_dir.glob(f"{prefix}_unrelaxed_rank_*.pdb"))
        return {
            "summary": summary,
            "scores": score_payloads,
            "pdb_names": pdb_names,
            "returned_keys": sorted(returned),
            "returned_rank": returned.get("rank"),
            "returned_complex_metrics": returned.get("complex_metrics"),
            "result_file_names": sorted(Path(path).name for path in returned.get("result_files", [])),
            "all_result_files_exist": all(Path(path).exists() for path in returned.get("result_files", [])),
        }


def contract():
    module = load_candidate()
    tree = ast.parse(BATCH.read_text(encoding="utf-8"), filename=str(BATCH))
    signatures = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in {
            "predict_structure", "run"
        }:
            signatures[node.name] = [argument.arg for argument in node.args.args]
    batch_text = BATCH.read_text(encoding="utf-8")
    return {
        "score_dockq": list(inspect.signature(module.score_dockq).parameters),
        "score_ipsae": list(inspect.signature(module.score_ipsae).parameters),
        "batch_signatures": signatures,
        "flags": {
            name: name in batch_text
            for name in (
                "--dockq-native-path",
                "--run-dockq",
                "--run-ipsae",
                "--ipsae-pae-cutoff",
                "--ipsae-distance-cutoff",
            )
        },
    }


def cli(payload):
    with tempfile.TemporaryDirectory(prefix="candidate-cli-") as temp_name:
        temp = Path(temp_name)
        model = temp / "model.pdb"
        native = temp / "native.pdb"
        scores = temp / "scores.json"
        output = temp / "output.json"
        model.write_text(pdb_text(payload["model"]), encoding="utf-8")
        command = [sys.executable, str(TARGET), "--model-pdb", str(model)]
        if payload.get("native") is not None:
            native.write_text(pdb_text(payload["native"]), encoding="utf-8")
            command.extend(["--native-pdb", str(native)])
        if payload.get("scores") is not None:
            scores.write_text(
                json.dumps(payload["scores"], allow_nan=False), encoding="utf-8"
            )
            command.extend(["--scores-json", str(scores)])
        command.extend(
            [
                "--pae-cutoff",
                str(payload.get("pae_cutoff", 15.0)),
                "--distance-cutoff",
                str(payload.get("distance_cutoff", 15.0)),
                "--output",
                str(output),
            ]
        )
        completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
        if completed.returncode:
            raise RuntimeError(
                f"CLI exited {completed.returncode}: {completed.stderr}\n{completed.stdout}"
            )
        text = output.read_text(encoding="utf-8")
        return {
            "value": json.loads(text),
            "standard_json": "NaN" not in text and "Infinity" not in text,
        }


def dispatch(mode, payload):
    if mode == "gate_import":
        module = load_candidate()
        if not callable(getattr(module, "score_dockq", None)):
            raise AssertionError("score_dockq is missing")
        if not callable(getattr(module, "score_ipsae", None)):
            raise AssertionError("score_ipsae is missing")
        isolation = {
            "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
            "reference_removed_or_unreadable": not os.access(
                "/tests/reference", os.R_OK
            ),
            "dockq_not_importable": importlib.util.find_spec("DockQ") is None,
            "ipsae_not_importable": importlib.util.find_spec("ipsae") is None,
            "no_agent_donor_paths": not Path("/opt/dockq").exists()
            and not Path("/opt/ipsae").exists(),
            "candidate_runner_outside_tests": str(Path(__file__).resolve())
            == "/opt/candidate-runner.py",
        }
        if not all(isolation.values()):
            raise AssertionError(f"candidate isolation failed: {isolation}")
        return {"contract": contract(), "isolation": isolation}
    if mode == "contract":
        return contract()
    if mode == "dockq":
        module = load_candidate()
        return module.score_dockq(
            pdb_text(payload["model"]),
            pdb_text(payload["native"]),
            payload.get("mapping"),
            payload.get("contact_cutoff", 5.0),
            payload.get("interface_cutoff", 10.0),
        )
    if mode == "ipsae":
        module = load_candidate()
        return module.score_ipsae(
            payload["scores"]["pae"],
            payload["scores"]["plddt"],
            pdb_text(payload["model"]),
            payload.get("pae_cutoff", 15.0),
            payload.get("distance_cutoff", 15.0),
            payload["scores"].get("iptm"),
        )
    if mode == "cli":
        return cli(payload)
    if mode == "workflow":
        return workflow(payload)
    raise ValueError(f"unknown mode: {mode}")


def main():
    mode = sys.argv[1]
    payload = json.load(sys.stdin)
    try:
        value = dispatch(mode, payload)
        print(json.dumps({"ok": True, "value": value}, allow_nan=False))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:2000],
                },
                allow_nan=False,
            )
        )


if __name__ == "__main__":
    main()
