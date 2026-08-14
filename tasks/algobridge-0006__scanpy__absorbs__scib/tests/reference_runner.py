#!/usr/bin/env python3
"""Run the locked pristine Scanpy -> scIB graph-LISI reference."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

from anndata import AnnData
import numpy as np
import pandas as pd
import scanpy
import scib
from scib.metrics.lisi import lisi_graph_py
from scipy import sparse
from scipy.sparse import csgraph


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


def effective_neighbors(graph, limit):
    _, memberships = csgraph.connected_components(graph, directed=False)
    sizes = np.bincount(memberships)
    return np.minimum(limit, sizes[memberships] - 1).astype(int)


def donor_scores(adata, key, *, n_neighbors, perplexity):
    raw = np.asarray(
        lisi_graph_py(
            adata,
            key,
            n_neighbors=n_neighbors,
            perplexity=perplexity,
            subsample=None,
            n_cores=1,
            verbose=False,
        ),
        dtype=np.float64,
    )
    nonempty = np.asarray(adata.obsp["connectivities"].getnnz(axis=1) > 0)
    if raw.shape != (int(nonempty.sum()),):
        raise RuntimeError(
            f"scIB returned {raw.size} rows for {int(nonempty.sum())} non-isolates"
        )
    result = np.ones(adata.n_obs, dtype=np.float64)
    result[nonempty] = raw
    return result


def run_case(spec):
    graph = decode_csr(spec)
    n = graph.shape[0]
    obs = pd.DataFrame(
        {
            "batch": spec["batch_labels"],
            "cell_type": spec["cell_type_labels"],
        },
        index=[f"cell-{index}" for index in range(n)],
    )
    adata = AnnData(X=np.zeros((n, 1), dtype=np.float32), obs=obs)
    adata.obsp["connectivities"] = graph.copy()
    adata.uns["neighbors"] = {"connectivities_key": "connectivities"}
    kwargs = {
        "n_neighbors": int(spec["n_neighbors"]),
        "perplexity": float(spec["perplexity"]),
    }
    ilisi = donor_scores(adata, "batch", **kwargs)
    clisi = donor_scores(adata, "cell_type", **kwargs)
    effective = effective_neighbors(graph, kwargs["n_neighbors"])
    return {
        "name": spec["name"],
        "ilisi": ilisi.tolist(),
        "clisi": clisi.tolist(),
        "effective_neighbors": effective.tolist(),
        "median_ilisi": float(np.median(ilisi)),
        "median_clisi": float(np.median(clisi)),
    }


def main():
    payload = json.load(sys.stdin)
    binary = Path(scib.__file__).parent / "knn_graph/knn_graph.o"
    results = [run_case(spec) for spec in payload["cases"]]
    json.dump(
        {
            "provenance": {
                "scanpy_version": importlib.metadata.version("scanpy"),
                "scanpy_file": scanpy.__file__,
                "scib_version": importlib.metadata.version("scib"),
                "scib_file": scib.__file__,
                "knn_graph_file": str(binary),
                "knn_graph_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "numpy_version": np.__version__,
            },
            "results": results,
        },
        sys.stdout,
        allow_nan=False,
    )


if __name__ == "__main__":
    main()

