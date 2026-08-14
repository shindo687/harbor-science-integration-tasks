#!/usr/bin/env python3
"""Run locked Scanpy AnnData through locked scVelo for fresh references."""

from __future__ import annotations

import contextlib
import importlib.metadata
import io
import json
import sys

import numpy as np
import scanpy
import scvelo

from protocol import build_adata, collect


def donor_kwargs(spec):
    gene_subset = spec.get("gene_subset")
    if gene_subset is not None and all(isinstance(value, bool) for value in gene_subset):
        gene_subset = [name for name, keep in zip(spec["var_names"], gene_subset) if keep]
    return {
        "vkey": "velocity",
        "xkey": "Ms",
        "n_neighbors": spec.get("n_neighbors"),
        "n_recurse_neighbors": int(spec["n_recurse_neighbors"]),
        "gene_subset": gene_subset,
        "sqrt_transform": bool(spec["sqrt_transform"]),
        "mode_neighbors": "distances",
        "n_jobs": 1,
        "backend": "threading",
        "show_progress_bar": False,
    }


def run_case(spec):
    adata = build_adata(spec)
    with contextlib.redirect_stdout(io.StringIO()):
        scvelo.tl.velocity_graph(adata, **donor_kwargs(spec))
    positive = adata.uns["velocity_graph"].tocsr()
    negative = adata.uns["velocity_graph_neg"].tocsr()
    self_transition = np.asarray(adata.obs["velocity_self_transition"], dtype=float)
    adata.obsp["velocity_graph"] = positive
    adata.obsp["velocity_graph_neg"] = negative
    # scVelo transition_matrix reads velocity graphs from .obsp when present.
    with contextlib.redirect_stdout(io.StringIO()):
        transition = scvelo.tl.transition_matrix(
            adata,
            vkey="velocity",
            scale=float(spec["transition_scale"]),
            use_negative_cosines=bool(spec["use_negative_cosines"]),
            self_transitions=True,
        ).tocsr()
    adata.obsp["velocity_transitions"] = transition
    confidence = np.asarray(positive.max(axis=1).toarray()).ravel()
    adata.obs["velocity_confidence"] = confidence
    adata.obs["velocity_self_transition"] = self_transition
    adata.uns["velocity_transition_params"] = {
        "neighbors_key": "neighbors",
        "n_neighbors": spec.get("n_neighbors"),
        "n_recurse_neighbors": int(spec["n_recurse_neighbors"]),
        "sqrt_transform": bool(spec["sqrt_transform"]),
        "transition_scale": float(spec["transition_scale"]),
        "use_negative_cosines": bool(spec["use_negative_cosines"]),
    }
    return collect(adata, spec["name"])


def main():
    payload = json.load(sys.stdin)
    results = [run_case(spec) for spec in payload["cases"]]
    json.dump(
        {
            "provenance": {
                "scanpy_file": scanpy.__file__,
                "scanpy_version": importlib.metadata.version("scanpy"),
                "scvelo_file": scvelo.__file__,
                "scvelo_version": importlib.metadata.version("scvelo"),
                "numpy_version": np.__version__,
            },
            "results": results,
        },
        sys.stdout,
        allow_nan=False,
    )


if __name__ == "__main__":
    main()
