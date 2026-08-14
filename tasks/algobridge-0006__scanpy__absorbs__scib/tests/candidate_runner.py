#!/usr/bin/env python3
"""Public-protocol runner installed outside verifier-private paths."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import sys
import traceback

import numpy as np
from scipy import sparse


def decode_csr(spec):
    encoded = spec["distances"]
    return sparse.csr_matrix(
        (
            np.asarray(encoded["data"], dtype=np.float64),
            np.asarray(encoded["indices"], dtype=np.int64),
            np.asarray(encoded["indptr"], dtype=np.int64),
        ),
        shape=tuple(encoded["shape"]),
    )


def finite_vector(value, name, size, *, integral=False):
    array = np.asarray(value)
    if array.shape != (size,):
        raise ValueError(f"{name} has shape {array.shape}, expected {(size,)}")
    if integral:
        numeric = np.asarray(array, dtype=np.float64)
        if not np.isfinite(numeric).all() or not np.equal(numeric, np.floor(numeric)).all():
            raise ValueError(f"{name} must contain finite integers")
        return numeric.astype(np.int64)
    array = np.asarray(array, dtype=np.float64)
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain finite values")
    return array


def run_case(function, spec):
    graph = decode_csr(spec)
    n = graph.shape[0]
    with contextlib.redirect_stdout(io.StringIO()):
        raw = function(
            graph,
            spec["batch_labels"],
            spec["cell_type_labels"],
            perplexity=spec["perplexity"],
            n_neighbors=spec["n_neighbors"],
        )
    if not isinstance(raw, dict):
        raise TypeError("lisi_graph_score must return a dict")
    required = {
        "ilisi",
        "clisi",
        "effective_neighbors",
        "median_ilisi",
        "median_clisi",
    }
    missing = required - raw.keys()
    if missing:
        raise KeyError(f"missing result fields: {sorted(missing)}")
    ilisi = finite_vector(raw["ilisi"], "ilisi", n)
    clisi = finite_vector(raw["clisi"], "clisi", n)
    effective = finite_vector(
        raw["effective_neighbors"], "effective_neighbors", n, integral=True
    )
    median_ilisi = float(raw["median_ilisi"])
    median_clisi = float(raw["median_clisi"])
    if not math.isfinite(median_ilisi) or not math.isfinite(median_clisi):
        raise ValueError("median outputs must be finite")
    if not np.isclose(median_ilisi, np.median(ilisi), rtol=0, atol=1e-12):
        raise ValueError("median_ilisi is inconsistent with ilisi")
    if not np.isclose(median_clisi, np.median(clisi), rtol=0, atol=1e-12):
        raise ValueError("median_clisi is inconsistent with clisi")
    batch_count = len(set(spec["batch_labels"]))
    type_count = len(set(spec["cell_type_labels"]))
    if np.any(ilisi < 1 - 1e-8) or np.any(ilisi > batch_count + 1e-8):
        raise ValueError("ilisi is outside its scientific bounds")
    if np.any(clisi < 1 - 1e-8) or np.any(clisi > type_count + 1e-8):
        raise ValueError("clisi is outside its scientific bounds")
    if np.any(effective < 0) or np.any(effective > int(spec["n_neighbors"])):
        raise ValueError("effective_neighbors is outside its valid range")
    return {
        "name": spec["name"],
        "ilisi": ilisi.tolist(),
        "clisi": clisi.tolist(),
        "effective_neighbors": effective.tolist(),
        "median_ilisi": median_ilisi,
        "median_clisi": median_clisi,
    }


def contract_checks(function):
    graph = sparse.csr_matrix(
        ([0.4, 0.4, 0.7, 0.7], ([0, 1, 1, 2], [1, 0, 2, 1])),
        shape=(3, 3),
    )
    labels = ["a", "b", "a"]
    probes = [
        ("dense_graph", lambda: function(graph.toarray(), labels, labels, n_neighbors=2, perplexity=1.5)),
        ("asymmetric_graph", lambda: function(sparse.triu(graph), labels, labels, n_neighbors=2, perplexity=1.5)),
        ("negative_distance", lambda: function(-graph, labels, labels, n_neighbors=2, perplexity=1.5)),
        ("label_length", lambda: function(graph, labels[:2], labels, n_neighbors=2, perplexity=1.5)),
        ("neighbor_count", lambda: function(graph, labels, labels, n_neighbors=3, perplexity=1.5)),
        ("perplexity_low", lambda: function(graph, labels, labels, n_neighbors=2, perplexity=1.0)),
        ("perplexity_high", lambda: function(graph, labels, labels, n_neighbors=2, perplexity=2.0)),
    ]
    checks = []
    for name, probe in probes:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                probe()
        except (TypeError, ValueError):
            checks.append({"name": name, "rejected": True})
        except Exception as error:
            checks.append({"name": name, "rejected": False, "wrong_error": type(error).__name__})
        else:
            checks.append({"name": name, "rejected": False})
    return checks


def main():
    payload = json.load(sys.stdin)
    try:
        sys.path.insert(0, "/opt/candidate-runtime")
        import scanpy
        from scanpy.metrics import lisi_graph_score

        module = importlib.util.find_spec(lisi_graph_score.__module__)
        if module is None or not str(module.origin).startswith("/opt/candidate-runtime/"):
            raise RuntimeError("lisi_graph_score is not implemented in Candidate Scanpy")
        if importlib.util.find_spec("scib") is not None:
            raise RuntimeError("scIB is importable in Candidate runtime")
        isolation = {
            "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
            "reference_runner_removed": not Path("/opt/reference-runner").exists(),
            "reference_venv_removed": not Path("/opt/reference-venv").exists(),
            "reference_host_removed": not Path("/opt/reference-host").exists(),
            "reference_donor_removed": not Path("/opt/reference-donor").exists(),
            "pristine_host_removed": not Path("/opt/pristine-host").exists(),
            "wheelhouse_removed": not Path("/opt/wheels").exists(),
            "candidate_tools_removed": not Path("/opt/candidate-tools").exists(),
            "scib_unavailable": importlib.util.find_spec("scib") is None,
        }
        results = []
        for case in payload["cases"]:
            try:
                results.append({"ok": True, "result": run_case(lisi_graph_score, case)})
            except Exception as error:
                results.append(
                    {
                        "ok": False,
                        "name": case.get("name"),
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
        response = {
            "fatal": None,
            "scanpy_file": scanpy.__file__,
            "lisi_module": module.origin,
            "results": results,
            "contract_checks": contract_checks(lisi_graph_score),
            "isolation_checks": isolation,
        }
    except Exception as error:
        response = {
            "fatal": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(limit=5),
            "results": [],
            "contract_checks": [],
            "isolation_checks": {},
        }
    json.dump(response, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()

