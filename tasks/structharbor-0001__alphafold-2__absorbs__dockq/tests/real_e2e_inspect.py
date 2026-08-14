#!/usr/bin/env python3
"""Extract bounded observations from a real AF2 output as the candidate uid."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import pickle


def jsonable(value):
  try:
    import numpy as np
    if isinstance(value, np.ndarray):
      return value.tolist()
    if isinstance(value, np.generic):
      return value.item()
  except ImportError:
    pass
  if isinstance(value, dict):
    return {str(key): jsonable(item) for key, item in value.items()}
  if isinstance(value, (list, tuple)):
    return [jsonable(item) for item in value]
  if value is None or isinstance(value, (str, int, float, bool)):
    return value
  return repr(value)


def main() -> None:
  parser = argparse.ArgumentParser()
  parser.add_argument("--output-dir", type=Path, required=True)
  parser.add_argument("--runner-name", required=True)
  parser.add_argument("--result-path", type=Path, required=True)
  args = parser.parse_args()

  output = args.output_dir
  with (output / f"result_{args.runner_name}.pkl").open("rb") as handle:
    result = pickle.load(handle)
  summary_text = (output / "dockq_scores.json").read_text(encoding="utf-8")
  summary = json.loads(summary_text)
  ranking = json.loads(
      (output / "ranking_debug.json").read_text(encoding="utf-8")
  )
  artifacts = {}
  for filename in (
      "features.pkl",
      f"result_{args.runner_name}.pkl",
      f"unrelaxed_{args.runner_name}.pdb",
      f"unrelaxed_{args.runner_name}.cif",
      f"confidence_{args.runner_name}.json",
      "ranking_debug.json",
      "timings.json",
      "ranked_0.pdb",
      "ranked_0.cif",
      "dockq_scores.json",
  ):
    path = output / filename
    artifacts[filename] = path.is_file() and path.stat().st_size > 0

  payload = {
      "result_keys": sorted(str(key) for key in result),
      "dockq_evaluation": jsonable(result.get("dockq_evaluation")),
      "summary": jsonable(summary),
      "summary_nonstandard_json": "NaN" in summary_text or "Infinity" in summary_text,
      "ranking": jsonable(ranking),
      "artifacts": artifacts,
  }
  args.result_path.write_text(
      json.dumps(payload, sort_keys=True, allow_nan=False) + "\n",
      encoding="utf-8",
  )


if __name__ == "__main__":
  main()
