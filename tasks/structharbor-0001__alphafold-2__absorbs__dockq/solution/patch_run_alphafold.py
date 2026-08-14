#!/usr/bin/env python3
"""Oracle-only deterministic patcher for AlphaFold 2 DockQ integration."""
from __future__ import annotations

from pathlib import Path
import sys


path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")


def replace_once(old: str, new: str, label: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one {label} anchor, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    "flags.DEFINE_boolean(\n    'use_gpu_relax',",
    "flags.DEFINE_string(\n"
    "    'dockq_native_path',\n"
    "    None,\n"
    "    'Native/reference PDB used for automatic DockQ evaluation.',\n"
    ")\n"
    "flags.DEFINE_boolean(\n"
    "    'run_dockq',\n"
    "    True,\n"
    "    'Evaluate every predicted model with DockQ when a native PDB is supplied.',\n"
    ")\n"
    "flags.DEFINE_boolean(\n    'use_gpu_relax',",
    "CLI flag insertion",
)

replace_once(
    "def predict_structure(\n",
    "def _empty_dockq_evaluation(status: str, reason: str | None) -> Dict[str, Any]:\n"
    "  return {\n"
    "      'status': status,\n"
    "      'reason': reason,\n"
    "      'dockq': None,\n"
    "      'fnat': None,\n"
    "      'irms': None,\n"
    "      'lrms': None,\n"
    "      'capri': None,\n"
    "      'native_contacts': None,\n"
    "      'preserved_contacts': None,\n"
    "      'mapping': None,\n"
    "  }\n\n\n"
    "def _computed_dockq_evaluation(metrics: Dict[str, Any]) -> Dict[str, Any]:\n"
    "  record = {\n"
    "      'status': 'computed',\n"
    "      'reason': None,\n"
    "      'dockq': float(metrics['DockQ']),\n"
    "      'fnat': float(metrics['fnat']),\n"
    "      'irms': float(metrics['iRMSD']),\n"
    "      'lrms': float(metrics['LRMSD']),\n"
    "      'capri': metrics['CAPRI'],\n"
    "      'native_contacts': int(metrics['native_contacts']),\n"
    "      'preserved_contacts': int(metrics['preserved_contacts']),\n"
    "      'mapping': dict(metrics['mapping']),\n"
    "  }\n"
    "  for key in ('dockq', 'fnat', 'irms', 'lrms'):\n"
    "    if not np.isfinite(record[key]):\n"
    "      raise ValueError(f'non-finite DockQ field: {key}')\n"
    "  return record\n\n\n"
    "def _write_dockq_summary(path: str, records: Dict[str, Any]) -> None:\n"
    "  with open(path, 'w') as f:\n"
    "    json.dump(records, f, indent=2, sort_keys=True, allow_nan=False)\n"
    "    f.write('\\n')\n\n\n"
    "def predict_structure(\n",
    "helper insertion",
)

replace_once(
    "    models_to_relax: ModelsToRelax,\n    model_type: str,\n):",
    "    models_to_relax: ModelsToRelax,\n"
    "    model_type: str,\n"
    "    dockq_native_path: str | None = None,\n"
    "    run_dockq: bool = True,\n"
    "):",
    "predict_structure signature",
)

replace_once(
    "  ranking_confidences = {}\n\n  # Run the models.",
    "  ranking_confidences = {}\n"
    "  dockq_scores = {}\n"
    "  dockq_errors = []\n"
    "  dockq_native_structure = None\n"
    "  dockq_native_error = None\n"
    "  if run_dockq and dockq_native_path:\n"
    "    try:\n"
    "      from alphafold.common import dockq_score\n"
    "      native_pdb = pathlib.Path(dockq_native_path).read_text()\n"
    "      native_protein = protein.from_pdb_string(native_pdb)\n"
    "      dockq_native_structure = dockq_score.protein_to_structure(native_protein)\n"
    "    except Exception as exc:\n"
    "      dockq_native_error = f'{type(exc).__name__}: {exc}'\n\n"
    "  # Run the models.",
    "DockQ setup insertion",
)

replace_once(
    "    # Save the model outputs.\n"
    "    result_output_path = os.path.join(output_dir, f'result_{model_name}.pkl')\n"
    "    with open(result_output_path, 'wb') as f:\n"
    "      pickle.dump(np_prediction_result, f, protocol=4)\n\n",
    "",
    "original result pickle block",
)

replace_once(
    "    unrelaxed_pdbs[model_name] = protein.to_pdb(unrelaxed_protein)\n"
    "    unrelaxed_pdb_path = os.path.join(output_dir, f'unrelaxed_{model_name}.pdb')",
    "    unrelaxed_pdbs[model_name] = protein.to_pdb(unrelaxed_protein)\n"
    "    if not run_dockq:\n"
    "      dockq_record = _empty_dockq_evaluation('disabled', 'disabled_by_user')\n"
    "    elif not dockq_native_path:\n"
    "      dockq_record = _empty_dockq_evaluation(\n"
    "          'not_computed', 'native_structure_not_provided')\n"
    "    elif dockq_native_error is not None:\n"
    "      dockq_record = _empty_dockq_evaluation('error', dockq_native_error)\n"
    "      dockq_errors.append(f'{model_name}: {dockq_native_error}')\n"
    "    else:\n"
    "      try:\n"
    "        from alphafold.common import dockq_score\n"
    "        model_structure = dockq_score.protein_to_structure(unrelaxed_protein)\n"
    "        metrics = dockq_score.score_complex(\n"
    "            model_structure, dockq_native_structure)\n"
    "        dockq_record = _computed_dockq_evaluation(metrics)\n"
    "      except Exception as exc:\n"
    "        reason = f'{type(exc).__name__}: {exc}'\n"
    "        dockq_record = _empty_dockq_evaluation('error', reason)\n"
    "        dockq_errors.append(f'{model_name}: {reason}')\n"
    "    np_prediction_result['dockq_evaluation'] = dockq_record\n"
    "    result_output_path = os.path.join(output_dir, f'result_{model_name}.pkl')\n"
    "    with open(result_output_path, 'wb') as f:\n"
    "      pickle.dump(np_prediction_result, f, protocol=4)\n"
    "    dockq_scores[model_name] = dockq_record\n"
    "    _write_dockq_summary(\n"
    "        os.path.join(output_dir, 'dockq_scores.json'), dockq_scores)\n\n"
    "    unrelaxed_pdb_path = os.path.join(output_dir, f'unrelaxed_{model_name}.pdb')",
    "per-model DockQ insertion",
)

replace_once(
    "  if models_to_relax != ModelsToRelax.NONE:\n"
    "    relax_metrics_path = os.path.join(output_dir, 'relax_metrics.json')\n"
    "    with open(relax_metrics_path, 'w') as f:\n"
    "      f.write(json.dumps(relax_metrics, indent=4))\n",
    "  if models_to_relax != ModelsToRelax.NONE:\n"
    "    relax_metrics_path = os.path.join(output_dir, 'relax_metrics.json')\n"
    "    with open(relax_metrics_path, 'w') as f:\n"
    "      f.write(json.dumps(relax_metrics, indent=4))\n"
    "  if dockq_errors:\n"
    "    raise RuntimeError('DockQ evaluation failed: ' + '; '.join(dockq_errors))\n",
    "deferred error insertion",
)

replace_once(
    "        models_to_relax=FLAGS.models_to_relax,\n"
    "        model_type=model_type,\n"
    "    )",
    "        models_to_relax=FLAGS.models_to_relax,\n"
    "        model_type=model_type,\n"
    "        dockq_native_path=FLAGS.dockq_native_path,\n"
    "        run_dockq=FLAGS.run_dockq,\n"
    "    )",
    "main call pass-through",
)

path.write_text(text, encoding="utf-8")
