"""Small public runner with the same output contract as the hidden verifier."""

from __future__ import annotations

from anndata import AnnData
import numpy as np
import pandas as pd
from scipy import sparse


def _embedding(spec):
    encoded = spec["embedding"]
    if encoded["format"] == "dense":
        return np.asarray(encoded["data"], dtype=float)
    return sparse.csr_matrix(
        (encoded["data"], encoded["indices"], encoded["indptr"]),
        shape=tuple(encoded["shape"]),
    )


def _encode(matrix):
    matrix = sparse.csr_matrix(matrix)
    matrix.sort_indices()
    return {
        "data": matrix.data.tolist(),
        "indices": matrix.indices.tolist(),
        "indptr": matrix.indptr.tolist(),
        "shape": list(matrix.shape),
    }


def run_case(function, spec):
    obs = pd.DataFrame(
        {spec["batch_key"]: spec["batches"]}, index=spec["cell_ids"]
    )
    adata = AnnData(np.zeros((len(obs), 1)), obs=obs)
    adata.obsm[spec["use_rep"]] = _embedding(spec)
    returned = function(
        adata,
        batch_key=spec["batch_key"],
        neighbors_within_batch=spec["neighbors_within_batch"],
        use_rep=spec["use_rep"],
        metric=spec["metric"],
        key_added=spec["key_added"],
        copy=spec["copy"],
    )
    target = returned if spec["copy"] else adata
    key = spec["key_added"]
    distance_key = "distances" if key == "neighbors" else f"{key}_distances"
    connectivity_key = "connectivities" if key == "neighbors" else f"{key}_connectivities"
    metadata = target.uns[key]
    return {
        "name": spec["name"],
        "cell_ids": target.obs_names.astype(str).tolist(),
        "batch_order": np.asarray(metadata["batch_order"]).astype(str).tolist(),
        "indices": np.asarray(metadata["indices"]).tolist(),
        "neighbor_distances": np.asarray(metadata["neighbor_distances"]).tolist(),
        "distances": _encode(target.obsp[distance_key]),
        "connectivities": _encode(target.obsp[connectivity_key]),
        "return_is_copy": spec["copy"],
    }

