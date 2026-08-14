#!/usr/bin/env python3
"""Oracle-only deterministic patcher for ColabFold v1.6.1."""
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
    "from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter\n",
    "from argparse import (\n"
    "    ArgumentParser, ArgumentDefaultsHelpFormatter, BooleanOptionalAction,\n"
    ")\n",
    "argparse import",
)


replace_once(
    "def predict_structure(\n",
    '''def _dockq_state(status: str, reason: Optional[str] = None, metrics=None):
    record = {
        "status": status, "reason": reason, "dockq": None, "fnat": None,
        "irms": None, "lrms": None, "capri": None, "native_contacts": None,
        "preserved_contacts": None, "mapping": None,
    }
    if metrics is not None:
        record.update({
            "dockq": float(metrics["DockQ"]), "fnat": float(metrics["fnat"]),
            "irms": float(metrics["iRMSD"]), "lrms": float(metrics["LRMSD"]),
            "capri": metrics["CAPRI"],
            "native_contacts": int(metrics["native_contacts"]),
            "preserved_contacts": int(metrics["preserved_contacts"]),
            "mapping": dict(metrics["mapping"]),
        })
    return record


def _ipsae_state(status: str, reason: Optional[str], pae_cutoff: float,
                 distance_cutoff: float, chain_pairs=None):
    return {
        "status": status, "reason": reason,
        "pae_cutoff": float(pae_cutoff),
        "distance_cutoff": float(distance_cutoff),
        "chain_pairs": [] if chain_pairs is None else chain_pairs,
    }


def _native_for_job(native_path: Optional[Union[str, Path]], prefix: str):
    if native_path is None:
        return None
    candidate = Path(native_path)
    if candidate.is_dir():
        candidate = candidate / f"{prefix}.pdb"
    return candidate


def predict_structure(
''',
    "metric helpers",
)

replace_once(
    "    calc_extra_ptm: bool = False,\n    use_probs_extra: bool = True,\n):",
    "    calc_extra_ptm: bool = False,\n"
    "    use_probs_extra: bool = True,\n"
    "    run_dockq: bool = True,\n"
    "    dockq_native_path: Optional[Union[str, Path]] = None,\n"
    "    run_ipsae: bool = True,\n"
    "    ipsae_pae_cutoff: float = 15.0,\n"
    "    ipsae_distance_cutoff: float = 15.0,\n"
    "):",
    "predict_structure signature",
)

replace_once(
    "    seq_len = sum(sequences_lengths)\n\n    # iterate through random seeds",
    '''    seq_len = sum(sequences_lengths)
    complex_metric_records = {}
    native_candidate = _native_for_job(dockq_native_path, prefix)
    native_text = None
    native_error = None
    if run_dockq and native_candidate is not None:
        try:
            native_text = native_candidate.read_text(encoding="utf-8")
        except Exception as exc:
            native_error = f"{type(exc).__name__}: {exc}"

    # iterate through random seeds''',
    "metric setup",
)

replace_once(
    '''            del plddt
            file = files.get("scores", "json")
''',
    '''            del plddt

            if not run_dockq:
                dockq_record = _dockq_state("disabled", "disabled_by_user")
            elif native_candidate is None:
                dockq_record = _dockq_state("not_computed", "native_structure_not_provided")
            elif native_error is not None:
                dockq_record = _dockq_state("error", native_error)
            else:
                try:
                    from colabfold.alphafold import complex_metrics
                    dockq_metrics = complex_metrics.score_dockq(protein_lines, native_text)
                    dockq_record = _dockq_state("computed", None, dockq_metrics)
                except Exception as exc:
                    dockq_record = _dockq_state("error", f"{type(exc).__name__}: {exc}")

            if not run_ipsae:
                ipsae_record = _ipsae_state(
                    "disabled", "disabled_by_user", ipsae_pae_cutoff, ipsae_distance_cutoff)
            elif not is_complex:
                ipsae_record = _ipsae_state(
                    "not_applicable", "single_chain_prediction",
                    ipsae_pae_cutoff, ipsae_distance_cutoff)
            elif "predicted_aligned_error" not in result:
                ipsae_record = _ipsae_state(
                    "not_computed", "predicted_aligned_error_not_available",
                    ipsae_pae_cutoff, ipsae_distance_cutoff)
            else:
                try:
                    from colabfold.alphafold import complex_metrics
                    ipsae_metrics = complex_metrics.score_ipsae(
                        result["predicted_aligned_error"][:seq_len, :seq_len],
                        result["plddt"][:seq_len], protein_lines,
                        pae_cutoff=ipsae_pae_cutoff,
                        distance_cutoff=ipsae_distance_cutoff,
                        iptm=conf[-1].get("iptm"),
                    )
                    ipsae_record = _ipsae_state(
                        "computed", None, ipsae_pae_cutoff, ipsae_distance_cutoff,
                        ipsae_metrics["chain_pairs"])
                except Exception as exc:
                    ipsae_record = _ipsae_state(
                        "error", f"{type(exc).__name__}: {exc}",
                        ipsae_pae_cutoff, ipsae_distance_cutoff)
            complex_record = {
                "schema_version": 1,
                "dockq": dockq_record,
                "ipsae": ipsae_record,
            }
            scores["complex_metrics"] = complex_record
            complex_metric_records[tag] = complex_record

            file = files.get("scores", "json")
''',
    "per-model metric calculation",
)

replace_once(
    '''    return {"rank":rank,
            "metric":metric,
            "result_files":result_files}
''',
    '''    summary = {
        rank_name: complex_metric_records[model_names[key]]
        for rank_name, key in zip(rank, model_rank)
    }
    summary_file = result_dir.joinpath(f"{prefix}_complex_metrics.json")
    summary_file.write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\\n")
    result_files.append(summary_file)

    return {"rank":rank,
            "metric":metric,
            "result_files":result_files,
            "complex_metrics":summary}
''',
    "summary output",
)

replace_once(
    "    max_template_hits: int = 20,\n    **kwargs\n):",
    "    max_template_hits: int = 20,\n"
    "    run_dockq: bool = True,\n"
    "    dockq_native_path: Optional[Union[str, Path]] = None,\n"
    "    run_ipsae: bool = True,\n"
    "    ipsae_pae_cutoff: float = 15.0,\n"
    "    ipsae_distance_cutoff: float = 15.0,\n"
    "    **kwargs\n):",
    "run signature",
)

replace_once(
    '''                    calc_extra_ptm=calc_extra_ptm,
                    use_probs_extra=use_probs_extra,
                )
''',
    '''                    calc_extra_ptm=calc_extra_ptm,
                    use_probs_extra=use_probs_extra,
                    run_dockq=run_dockq,
                    dockq_native_path=dockq_native_path,
                    run_ipsae=run_ipsae,
                    ipsae_pae_cutoff=ipsae_pae_cutoff,
                    ipsae_distance_cutoff=ipsae_distance_cutoff,
                )
''',
    "run to prediction pass-through",
)

replace_once(
    '''    output_group.add_argument(
        "--rank",
''',
    '''    output_group.add_argument(
        "--dockq-native-path",
        default=None,
        help="Reference PDB, or directory containing <jobname>.pdb, for DockQ.",
    )
    output_group.add_argument(
        "--run-dockq", action=BooleanOptionalAction,
        default=True, help="Automatically evaluate DockQ when a native PDB is available.",
    )
    output_group.add_argument(
        "--run-ipsae", action=BooleanOptionalAction,
        default=True, help="Automatically calculate ipSAE for multimer predictions.",
    )
    output_group.add_argument("--ipsae-pae-cutoff", type=float, default=15.0)
    output_group.add_argument("--ipsae-distance-cutoff", type=float, default=15.0)
    output_group.add_argument(
        "--rank",
''',
    "CLI arguments",
)

replace_once(
    '''        max_template_hits=args.max_template_hits,
    )
''',
    '''        max_template_hits=args.max_template_hits,
        run_dockq=args.run_dockq,
        dockq_native_path=args.dockq_native_path,
        run_ipsae=args.run_ipsae,
        ipsae_pae_cutoff=args.ipsae_pae_cutoff,
        ipsae_distance_cutoff=args.ipsae_distance_cutoff,
    )
''',
    "main pass-through",
)

path.write_text(text, encoding="utf-8")
