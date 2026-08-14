#!/usr/bin/env python3
"""Public-protocol runner installed outside the verifier-private directory."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import math
import os
import pathlib
import sys
import traceback

import numpy as np


def stable_key(node):
    return (type(node).__module__, type(node).__qualname__, repr(node))


def build_graph(nx, spec):
    graph = nx.Graph()
    graph.add_nodes_from(spec["nodes"])
    graph.add_weighted_edges_from(spec["edges"], weight="weight")
    return graph


def finite_array(value, name, ndim):
    array = np.asarray(value, dtype=float)
    if array.ndim != ndim or not np.isfinite(array).all():
        raise ValueError(f"{name} must be a finite {ndim}-D numeric array")
    return array


def run_case(nx, spec):
    graph = build_graph(nx, spec)
    with contextlib.redirect_stdout(io.StringIO()):
        result = nx.spectral_clustering(
            graph,
            spec["n_clusters"],
            weight="weight",
            assign_labels="kmeans",
            seed=spec["seed"],
            eigen_tol=spec["eigen_tol"],
        )
    if not isinstance(result, dict):
        raise TypeError("spectral_clustering must return a dict")
    required = {"nodes", "partition", "eigenvalues", "embedding", "normalized_cut"}
    missing = required - result.keys()
    if missing:
        raise KeyError(f"missing result fields: {sorted(missing)}")

    result_nodes = list(result["nodes"])
    if len(result_nodes) != len(graph) or set(result_nodes) != set(graph):
        raise ValueError("result nodes must contain every graph node exactly once")
    canonical_nodes = sorted(graph, key=stable_key)
    row_by_node = {node: index for index, node in enumerate(result_nodes)}
    embedding = finite_array(result["embedding"], "embedding", 2)
    if embedding.shape != (len(graph), spec["n_clusters"]):
        raise ValueError(f"unexpected embedding shape {embedding.shape}")
    embedding = embedding[[row_by_node[node] for node in canonical_nodes], :]

    partition = result["partition"]
    if not isinstance(partition, dict) or set(partition) != set(graph):
        raise ValueError("partition must map every graph node exactly once")
    labels = [int(partition[node]) for node in canonical_nodes]
    if len(set(labels)) != spec["n_clusters"]:
        raise ValueError("partition must contain exactly n_clusters non-empty clusters")
    eigenvalues = finite_array(result["eigenvalues"], "eigenvalues", 1)
    if eigenvalues.shape != (spec["n_clusters"],):
        raise ValueError(f"unexpected eigenvalue shape {eigenvalues.shape}")
    score = float(result["normalized_cut"])
    if not math.isfinite(score):
        raise ValueError("normalized_cut must be finite")
    return {
        "name": spec["name"],
        "nodes": canonical_nodes,
        "labels": labels,
        "eigenvalues": eigenvalues.tolist(),
        "embedding": embedding.tolist(),
        "normalized_cut": score,
    }


def contract_checks(nx):
    checks = []

    directed = nx.DiGraph()
    directed.add_edge(0, 1, weight=1.0)
    multigraph = nx.MultiGraph()
    multigraph.add_edge(0, 1, weight=1.0)
    negative = nx.Graph()
    negative.add_edge(0, 1, weight=-1.0)
    valid = nx.path_graph(4)
    probes = [
        ("directed", lambda: nx.spectral_clustering(directed, 2)),
        ("multigraph", lambda: nx.spectral_clustering(multigraph, 2)),
        ("negative_weight", lambda: nx.spectral_clustering(negative, 2)),
        (
            "assign_labels",
            lambda: nx.spectral_clustering(valid, 2, assign_labels="discretize"),
        ),
        ("cluster_count", lambda: nx.spectral_clustering(valid, 5)),
    ]
    for name, probe in probes:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                probe()
        except Exception:
            checks.append({"name": name, "rejected": True})
        else:
            checks.append({"name": name, "rejected": False})
    return checks


def main():
    payload = json.load(sys.stdin)
    try:
        sys.path.insert(0, "/testbed")
        import networkx as nx

        if pathlib.Path(nx.__file__).resolve().is_relative_to(pathlib.Path("/opt/reference")):
            raise RuntimeError("candidate imported verifier reference NetworkX")
        if not hasattr(nx, "spectral_clustering"):
            raise AttributeError("networkx.spectral_clustering is missing")
        if not hasattr(nx.community, "spectral_clustering"):
            raise AttributeError("networkx.community.spectral_clustering is missing")
        if importlib.util.find_spec("sklearn") is not None:
            raise RuntimeError("scikit-learn is importable in candidate runtime")
        isolation_checks = {
            "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
            "reference_runner_unreadable": not os.access(
                "/opt/reference-runner/reference_runner.py", os.R_OK
            ),
            "reference_host_removed": not pathlib.Path("/opt/reference-host").exists(),
            "reference_venv_removed": not pathlib.Path("/opt/reference-venv").exists(),
            "wheelhouse_removed": not pathlib.Path("/opt/wheels").exists(),
        }

        results = []
        for spec in payload["cases"]:
            try:
                results.append({"ok": True, "result": run_case(nx, spec)})
            except Exception as error:
                results.append(
                    {
                        "ok": False,
                        "name": spec.get("name"),
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
        response = {
            "fatal": None,
            "networkx_file": nx.__file__,
            "networkx_version": nx.__version__,
            "results": results,
            "contract_checks": contract_checks(nx),
            "isolation_checks": isolation_checks,
        }
    except Exception as error:
        response = {
            "fatal": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(limit=4),
            "results": [],
            "contract_checks": [],
            "isolation_checks": {},
        }
    json.dump(response, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
