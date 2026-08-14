#!/usr/bin/env python3
"""Run one bounded, real AlphaFold-Multimer inference for the verifier.

This program intentionally constructs the official AlphaFold DataPipeline and
RunModel classes.  The verifier executes it once against pristine AlphaFold and
once against the candidate tree; no fake pipeline or fake model participates in
this path.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time
import typing

import typing_extensions


# The locked AF2 commit uses the Python 3.11 spelling while the CUDA 12.2
# verifier base provides Python 3.10.  This is a runtime typing-only decorator;
# supplying its standard backport does not alter model execution or results.
if not hasattr(typing, "dataclass_transform"):
  typing.dataclass_transform = typing_extensions.dataclass_transform


MODEL_NAME = "model_1_multimer_v3"
RUNNER_NAME = f"{MODEL_NAME}_pred_0"


def stockholm(sequence: str) -> str:
  return (
      "# STOCKHOLM 1.0\n"
      f"query {sequence}\n"
      f"#=GC RF {'x' * len(sequence)}\n"
      "//\n"
  )


def parse_fasta(path: Path) -> list[str]:
  sequences: list[str] = []
  current: list[str] = []
  for raw_line in path.read_text(encoding="utf-8").splitlines():
    line = raw_line.strip()
    if not line:
      continue
    if line.startswith(">"):
      if current:
        sequences.append("".join(current))
        current = []
    else:
      current.append(line)
  if current:
    sequences.append("".join(current))
  if len(sequences) != 2 or len(set(sequences)) != 2:
    raise ValueError("real E2E fixture must contain two sequence-distinct chains")
  return sequences


def require_tool(name: str, tool_dir: Path | None) -> str:
  candidate = tool_dir / name if tool_dir is not None else None
  resolved = str(candidate) if candidate is not None and candidate.is_file() else shutil.which(name)
  if not resolved:
    raise RuntimeError(f"required real data-pipeline executable is missing: {name}")
  return resolved


def prepare_pipeline_inputs(
    fasta_path: Path,
    fasta_name: str,
    output_root: Path,
    fixture_root: Path,
) -> None:
  sequences = parse_fasta(fasta_path)
  for chain_id, sequence in zip(("A", "B"), sequences):
    msa_dir = output_root / fasta_name / "msas" / chain_id
    msa_dir.mkdir(parents=True, exist_ok=True)
    text = stockholm(sequence)
    for filename in (
        "uniref90_hits.sto",
        "mgnify_hits.sto",
        "small_bfd_hits.sto",
        "uniprot_hits.sto",
    ):
      (msa_dir / filename).write_text(text, encoding="utf-8")

  # The exact-sequence template hits are rejected by AlphaFold's official
  # duplicate prefilter.  This still exercises real hmmbuild+hmmsearch and the
  # real template featurizer while preventing target/template leakage.
  (fixture_root / "pdb_seqres.fasta").write_text(
      f">9zza_A mol:protein length:{len(sequences[0])}\n{sequences[0]}\n"
      f">9zzb_A mol:protein length:{len(sequences[1])}\n{sequences[1]}\n",
      encoding="utf-8",
  )
  (fixture_root / "dummy_sequence_database.fasta").write_text(
      ">dummy\nACDEFGHIKLMNPQRSTVWY\n", encoding="utf-8"
  )
  mmcif_dir = fixture_root / "mmcif"
  mmcif_dir.mkdir(parents=True, exist_ok=True)
  # Constructor-level existence check only; duplicate hits are filtered before
  # this placeholder could be parsed.
  (mmcif_dir / "placeholder.cif").write_text(
      "data_placeholder\n#\n", encoding="utf-8"
  )


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--source-root", type=Path, required=True)
  parser.add_argument("--fasta-path", type=Path, required=True)
  parser.add_argument("--fasta-name", required=True)
  parser.add_argument("--native-path", type=Path, required=True)
  parser.add_argument("--output-root", type=Path, required=True)
  parser.add_argument("--fixture-root", type=Path, required=True)
  parser.add_argument("--data-root", type=Path, required=True)
  parser.add_argument("--metadata-path", type=Path, required=True)
  parser.add_argument("--integrated", action="store_true")
  parser.add_argument("--tool-dir", type=Path)
  args = parser.parse_args()

  source_root = args.source_root.resolve()
  sys.path.insert(0, str(source_root))

  from absl import logging
  import jax
  import numpy as np
  from alphafold.data import pipeline
  from alphafold.data import pipeline_multimer
  from alphafold.data import templates
  from alphafold.data.tools import hmmsearch
  from alphafold.model import config
  from alphafold.model import data
  from alphafold.model import model
  import run_alphafold

  logging.set_verbosity(logging.INFO)
  started = time.time()
  devices = [str(device) for device in jax.devices()]
  if not any(getattr(device, "platform", "").lower() in {"gpu", "cuda"} for device in jax.devices()):
    raise RuntimeError(f"real E2E requires a JAX GPU, discovered: {devices}")

  args.output_root.mkdir(parents=True, exist_ok=True)
  args.fixture_root.mkdir(parents=True, exist_ok=True)
  prepare_pipeline_inputs(
      args.fasta_path, args.fasta_name, args.output_root, args.fixture_root
  )
  tool_dir = args.tool_dir.resolve() if args.tool_dir else None
  template_searcher = hmmsearch.Hmmsearch(
      binary_path=require_tool("hmmsearch", tool_dir),
      hmmbuild_binary_path=require_tool("hmmbuild", tool_dir),
      database_path=str(args.fixture_root / "pdb_seqres.fasta"),
      cpu=2,
  )
  template_featurizer = templates.HmmsearchHitFeaturizer(
      mmcif_dir=str(args.fixture_root / "mmcif"),
      max_template_date="1900-01-01",
      max_hits=4,
      kalign_binary_path=require_tool("kalign", tool_dir),
      release_dates_path=None,
      obsolete_pdbs_path=str(args.data_root / "obsolete.dat"),
  )
  dummy_db = str(args.fixture_root / "dummy_sequence_database.fasta")
  monomer_pipeline = pipeline.DataPipeline(
      jackhmmer_binary_path=require_tool("jackhmmer", tool_dir),
      hhblits_binary_path="/unused/hhblits",
      uniref90_database_path=dummy_db,
      mgnify_database_path=dummy_db,
      bfd_database_path=None,
      uniref30_database_path=None,
      small_bfd_database_path=dummy_db,
      template_searcher=template_searcher,
      template_featurizer=template_featurizer,
      use_small_bfd=True,
      use_precomputed_msas=True,
      msa_tools_n_cpu=2,
  )
  data_pipeline = pipeline_multimer.DataPipeline(
      monomer_data_pipeline=monomer_pipeline,
      jackhmmer_binary_path=require_tool("jackhmmer", tool_dir),
      uniprot_database_path=dummy_db,
      use_precomputed_msas=True,
      jackhmmer_n_cpu=2,
  )

  model_config = config.model_config(MODEL_NAME)
  model_config.model.num_ensemble_eval = 1
  model_config.model.num_recycle = 1
  model_params = data.get_model_haiku_params(MODEL_NAME, str(args.data_root))
  model_runner = model.RunModel(model_config, model_params)

  if type(data_pipeline).__module__ != "alphafold.data.pipeline_multimer":
    raise RuntimeError(f"non-official DataPipeline: {type(data_pipeline)!r}")
  if type(model_runner).__module__ != "alphafold.model.model":
    raise RuntimeError(f"non-official RunModel: {type(model_runner)!r}")

  predict_args = dict(
      fasta_path=str(args.fasta_path),
      fasta_name=args.fasta_name,
      output_dir_base=str(args.output_root),
      data_pipeline=data_pipeline,
      model_runners={RUNNER_NAME: model_runner},
      amber_relaxer=None,
      benchmark=False,
      random_seed=20260813,
      models_to_relax=run_alphafold.ModelsToRelax.NONE,
      model_type="Multimer",
  )
  if args.integrated:
    predict_args.update(
        dockq_native_path=str(args.native_path),
        run_dockq=True,
    )
  run_alphafold.predict_structure(**predict_args)

  output_dir = args.output_root / args.fasta_name
  required = [
      output_dir / f"unrelaxed_{RUNNER_NAME}.pdb",
      output_dir / f"result_{RUNNER_NAME}.pkl",
      output_dir / "ranking_debug.json",
      output_dir / "timings.json",
      output_dir / "features.pkl",
  ]
  missing = [str(path) for path in required if not path.is_file() or path.stat().st_size == 0]
  if missing:
    raise RuntimeError(f"real AlphaFold run omitted required artifacts: {missing}")

  metadata = {
      "schema_version": 1,
      "elapsed_seconds": time.time() - started,
      "jax_version": jax.__version__,
      "numpy_version": np.__version__,
      "jax_devices": devices,
      "data_pipeline_class": f"{type(data_pipeline).__module__}.{type(data_pipeline).__name__}",
      "model_runner_class": f"{type(model_runner).__module__}.{type(model_runner).__name__}",
      "model_name": MODEL_NAME,
      "runner_name": RUNNER_NAME,
      "num_recycle": int(model_config.model.num_recycle),
      "num_ensemble_eval": int(model_config.model.num_ensemble_eval),
      "precomputed_msa": "query-only Stockholm parsed by official DataPipeline",
      "template_search": "real hmmbuild+hmmsearch with duplicate-hit leakage guard",
      "integrated": bool(args.integrated),
  }
  args.metadata_path.write_text(
      json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
  )
  print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
  main()
