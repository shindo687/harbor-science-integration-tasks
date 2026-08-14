#!/usr/bin/env python3
"""Run the locked Scanpy -> BBKNN reference for ALGOBRIDGE-0001."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import types

import numpy as np
from scipy import sparse
from scipy.spatial import cKDTree, distance

from protocol import decode_embedding, encode_csr


# BBKNN imports AnnoyIndex unconditionally although exact cKDTree/KDTree paths do
# not use it.  Keep the reference faithful while making that optional import
# explicit; attempting to instantiate the shim is a hard error.
annoy = types.ModuleType("annoy")


class _UnusedAnnoyIndex:
    def __init__(self, *args, **kwargs):
        raise RuntimeError("Annoy is outside the exact-search task boundary")


annoy.AnnoyIndex = _UnusedAnnoyIndex
sys.modules["annoy"] = annoy

from bbknn import matrix as donor  # noqa: E402


DONOR_MATRIX = Path(donor.__file__).resolve()


def canonical_exact(pca, batch_list, cell_ids, metric, k, *, donor_exact):
    batches = sorted(set(batch_list))
    n = len(cell_ids)
    donor_distances = donor_indices = None
    if metric == "euclidean" and donor_exact:
        # Exercise the locked donor's exact batch-quota search directly.  The
        # non-tie differential fixtures make its k-result unambiguous.
        donor_distances, donor_indices = donor.get_graph(
            pca=pca,
            batch_list=np.asarray(batch_list, dtype=str),
            params={
                "computation": "cKDTree",
                "metric": "euclidean",
                "neighbors_within_batch": k,
                "n_pcs": pca.shape[1],
            },
        )
        donor_distances = donor_distances.reshape(n, len(batches), k)
        donor_indices = donor_indices.reshape(n, len(batches), k)
    indices = np.empty((n, len(batches), k), dtype=np.int64)
    distances = np.empty((n, len(batches), k), dtype=np.float64)
    for batch_position, batch in enumerate(batches):
        pool = np.flatnonzero(np.asarray(batch_list) == batch)
        if donor_indices is not None:
            candidates = donor_indices[:, batch_position, :]
            all_distances = donor_distances[:, batch_position, :]
        elif metric == "euclidean":
            # The locked donor's exact backend and query operation.
            tree = cKDTree(pca[pool])
            all_distances, local = tree.query(pca, k=len(pool), workers=1)
            all_distances = np.asarray(all_distances).reshape(n, len(pool))
            local = np.asarray(local).reshape(n, len(pool))
            candidates = pool[local]
        else:
            # BBKNN's exact KDTree backend cannot express cosine.  The bounded
            # task requires exact cosine, so compute the original metric over
            # the batch pool, then feed its exact kNN result into the donor's
            # own graph construction below.
            all_distances = distance.cdist(pca, pca[pool], metric="cosine")
            candidates = np.broadcast_to(pool, all_distances.shape)
        for row in range(n):
            order = sorted(
                range(candidates.shape[1]),
                key=lambda position: (
                    float(all_distances[row, position]),
                    cell_ids[int(candidates[row, position])],
                ),
            )[:k]
            indices[row, batch_position] = candidates[row, order]
            distances[row, batch_position] = all_distances[row, order]
    return batches, indices, distances


def run_case(spec):
    raw = decode_embedding(spec)
    pca = raw.toarray() if sparse.issparse(raw) else np.asarray(raw, dtype=np.float64)
    batches = [str(value) for value in spec["batches"]]
    cell_ids = [str(value) for value in spec["cell_ids"]]
    k = int(spec["neighbors_within_batch"])
    metric = spec["metric"]
    # Locked BBKNN 1.6.0 exposes cKDTree's one-dimensional k=1 result without
    # normalizing its shape, so get_graph cannot assign it to a 2-D slice.
    # Preserve k=1 in the task contract via the same exact bounded selector.
    donor_exact = (
        metric == "euclidean"
        and k > 1
        and not spec.get("canonical_ties", False)
    )
    batch_order, per_batch_indices, per_batch_distances = canonical_exact(
        pca, batches, cell_ids, metric, k, donor_exact=donor_exact
    )
    n = len(cell_ids)
    # The graph order is global-by-distance, while the public tensor remains
    # grouped by batch.  Copies are essential: reshape would otherwise expose
    # a view and silently destroy the per-batch output contract during sorting.
    flat_indices = per_batch_indices.reshape(n, -1).copy()
    flat_distances = per_batch_distances.reshape(n, -1).copy()
    for row in range(n):
        order = sorted(
            range(flat_indices.shape[1]),
            key=lambda position: (
                float(flat_distances[row, position]),
                cell_ids[int(flat_indices[row, position])],
            ),
        )
        flat_indices[row] = flat_indices[row, order]
        flat_distances[row] = flat_distances[row, order]
    distances, connectivities = donor.compute_connectivities_umap(
        flat_indices,
        flat_distances,
        n,
        flat_indices.shape[1],
        set_op_mix_ratio=1.0,
        local_connectivity=1.0,
    )
    return {
        "name": spec["name"],
        "cell_ids": cell_ids,
        "batch_order": batch_order,
        "indices": per_batch_indices.tolist(),
        "neighbor_distances": per_batch_distances.tolist(),
        "distances": encode_csr(distances),
        "connectivities": encode_csr(connectivities),
        "return_is_copy": bool(spec.get("copy", False)),
        "selection_backend": (
            "locked_bbknn.get_graph[cKDTree]"
            if donor_exact
            else f"bounded_exact_{metric}"
        ),
    }


def main():
    payload = json.load(sys.stdin)
    results = [run_case(case) for case in payload["cases"]]
    json.dump(
        {
            "provenance": {
                "scanpy_version": importlib.metadata.version("scanpy"),
                "bbknn_source": str(DONOR_MATRIX),
                "bbknn_matrix_sha256": hashlib.sha256(DONOR_MATRIX.read_bytes()).hexdigest(),
                "numpy_version": np.__version__,
            },
            "results": results,
        },
        sys.stdout,
        allow_nan=False,
    )


if __name__ == "__main__":
    main()
