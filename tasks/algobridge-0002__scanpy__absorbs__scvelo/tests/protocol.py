"""Shared serialization and validation helpers used by the two runners."""

from __future__ import annotations

import numpy as np
from scipy import sparse

def decode_csr(encoded):
    return sparse.csr_matrix(
        (
            np.asarray(encoded["data"], dtype=np.float64),
            np.asarray(encoded["indices"], dtype=np.int64),
            np.asarray(encoded["indptr"], dtype=np.int64),
        ),
        shape=tuple(encoded["shape"]),
    )


def build_adata(spec):
    from anndata import AnnData

    X = np.asarray(spec["X"], dtype=np.float64)
    Mu = np.asarray(spec["Mu"], dtype=np.float64)
    V = np.asarray(spec["V"], dtype=np.float64)
    adata = AnnData(X=np.zeros_like(X))
    adata.obs_names = [f"cell-{i}" for i in range(len(X))]
    adata.var_names = spec["var_names"]
    adata.layers["Ms"] = X
    adata.layers["Mu"] = Mu
    adata.layers["velocity"] = V
    adata.obsp["distances"] = decode_csr(spec["distances"])
    adata.uns["neighbors"] = {
        "distances_key": "distances",
        "params": {"n_neighbors": int(max(1, adata.obsp["distances"].getnnz(axis=1).min()))},
    }
    return adata


def kwargs(spec):
    return {
        "vkey": "velocity",
        "xkey": "Ms",
        "neighbors_key": "neighbors",
        "n_neighbors": spec.get("n_neighbors"),
        "n_recurse_neighbors": int(spec["n_recurse_neighbors"]),
        "gene_subset": spec.get("gene_subset"),
        "sqrt_transform": bool(spec["sqrt_transform"]),
        "transition_scale": float(spec["transition_scale"]),
        "use_negative_cosines": bool(spec["use_negative_cosines"]),
    }


def canonical_csr(matrix):
    if not sparse.issparse(matrix):
        raise TypeError("output graph must be sparse")
    matrix = sparse.csr_matrix(matrix, dtype=np.float64)
    matrix.sort_indices()
    if matrix.shape[0] != matrix.shape[1] or not np.isfinite(matrix.data).all():
        raise ValueError("output graph must be square and finite")
    return {
        "data": matrix.data.tolist(),
        "indices": matrix.indices.tolist(),
        "indptr": matrix.indptr.tolist(),
        "shape": list(matrix.shape),
    }


def collect(adata, name):
    positive = sparse.csr_matrix(adata.obsp["velocity_graph"])
    negative = sparse.csr_matrix(adata.obsp["velocity_graph_neg"])
    transition = sparse.csr_matrix(adata.obsp["velocity_transitions"])
    confidence = np.asarray(adata.obs["velocity_confidence"], dtype=np.float64)
    self_transition = np.asarray(adata.obs["velocity_self_transition"], dtype=np.float64)
    n = adata.n_obs
    if confidence.shape != (n,) or self_transition.shape != (n,):
        raise ValueError("per-cell outputs have invalid shapes")
    if not np.isfinite(confidence).all() or not np.isfinite(self_transition).all():
        raise ValueError("per-cell outputs must be finite")
    return {
        "name": name,
        "positive": canonical_csr(positive),
        "negative": canonical_csr(negative),
        "transition": canonical_csr(transition),
        "confidence": confidence.tolist(),
        "self_transition": self_transition.tolist(),
        "params": dict(adata.uns["velocity_transition_params"]),
        "row_sums": np.asarray(transition.sum(axis=1)).ravel().tolist(),
        "absolute_row_sums": np.asarray(abs(transition).sum(axis=1)).ravel().tolist(),
        "positive_min": float(positive.data.min()) if positive.nnz else 0.0,
        "negative_max": float(negative.data.max()) if negative.nnz else 0.0,
        "support_overlap": int(positive.multiply(negative != 0).nnz),
    }
