"""Batch-balanced exact nearest-neighbor graphs."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

import numpy as np
from scipy import sparse
from scipy.spatial import distance

from ..neighbors._connectivity import umap

if TYPE_CHECKING:
    from anndata import AnnData
    from numpy.typing import NDArray


def _validate_embedding(adata: AnnData, use_rep: str) -> NDArray[np.float64]:
    if use_rep not in adata.obsm:
        raise KeyError(f"Did not find {use_rep!r} in adata.obsm")
    representation = adata.obsm[use_rep]
    if sparse.issparse(representation):
        representation = representation.toarray()
    embedding = np.asarray(representation, dtype=np.float64)
    if embedding.ndim != 2 or embedding.shape[0] != adata.n_obs:
        msg = "The selected representation must be a two-dimensional n_obs-by-features matrix."
        raise ValueError(msg)
    if embedding.shape[1] == 0 or not np.isfinite(embedding).all():
        msg = "The selected representation must have features and contain only finite values."
        raise ValueError(msg)
    return embedding


def _validate_batches(
    adata: AnnData, batch_key: str, neighbors_within_batch: int
) -> tuple[NDArray[np.str_], list[str]]:
    if batch_key not in adata.obs:
        raise KeyError(f"Did not find {batch_key!r} in adata.obs")
    if isinstance(neighbors_within_batch, bool) or not isinstance(
        neighbors_within_batch, (int, np.integer)
    ):
        raise TypeError("neighbors_within_batch must be a positive integer")
    if neighbors_within_batch <= 0:
        raise ValueError("neighbors_within_batch must be a positive integer")
    raw = adata.obs[batch_key].to_numpy()
    if any(not isinstance(value, str) or not value for value in raw):
        raise ValueError("batch labels must be nonempty strings")
    batches = np.asarray(raw, dtype=str)
    order, counts = np.unique(batches, return_counts=True)
    if len(order) == 0:
        raise ValueError("at least one batch is required")
    if int(counts.min()) < neighbors_within_batch:
        raise ValueError(
            "every batch must contain at least neighbors_within_batch observations"
        )
    return batches, order.tolist()


def _select_neighbors(
    embedding: NDArray[np.float64],
    batches: NDArray[np.str_],
    batch_order: list[str],
    cell_ids: NDArray[np.str_],
    metric: Literal["euclidean", "cosine"],
    neighbors_within_batch: int,
) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    n_obs = embedding.shape[0]
    indices = np.empty(
        (n_obs, len(batch_order), neighbors_within_batch), dtype=np.int64
    )
    distances = np.empty(indices.shape, dtype=np.float64)
    for batch_position, batch in enumerate(batch_order):
        pool = np.flatnonzero(batches == batch)
        pairwise = distance.cdist(embedding, embedding[pool], metric=metric)
        if metric == "cosine":
            pairwise = np.clip(pairwise, 0.0, 2.0)
        for row in range(n_obs):
            order = sorted(
                range(len(pool)),
                key=lambda position: (
                    float(pairwise[row, position]),
                    cell_ids[pool[position]],
                ),
            )[:neighbors_within_batch]
            indices[row, batch_position] = pool[order]
            distances[row, batch_position] = pairwise[row, order]
    return indices, distances


def _flatten_for_graph(
    indices: NDArray[np.int64],
    distances: NDArray[np.float64],
    cell_ids: NDArray[np.str_],
) -> tuple[NDArray[np.int64], NDArray[np.float64]]:
    n_obs = indices.shape[0]
    flat_indices = indices.reshape(n_obs, -1).copy()
    flat_distances = distances.reshape(n_obs, -1).copy()
    for row in range(n_obs):
        order = sorted(
            range(flat_indices.shape[1]),
            key=lambda position: (
                float(flat_distances[row, position]),
                cell_ids[flat_indices[row, position]],
            ),
        )
        flat_indices[row] = flat_indices[row, order]
        flat_distances[row] = flat_distances[row, order]
    return flat_indices, flat_distances


def _distance_graph(
    indices: NDArray[np.int64], distances: NDArray[np.float64], n_obs: int
) -> sparse.csr_matrix:
    rows = np.repeat(np.arange(n_obs, dtype=np.int64), indices.shape[1])
    graph = sparse.coo_matrix(
        (distances.ravel(), (rows, indices.ravel())), shape=(n_obs, n_obs)
    ).tocsr()
    graph.eliminate_zeros()
    graph.sort_indices()
    return graph


def batch_balanced_neighbors(
    adata: AnnData,
    *,
    batch_key: str,
    neighbors_within_batch: int = 3,
    use_rep: str = "X_pca",
    metric: Literal["euclidean", "cosine"] = "euclidean",
    key_added: str = "neighbors",
    copy: bool = False,
) -> AnnData | None:
    """Compute an exact, quota-balanced nearest-neighbor graph.

    Each observation receives the same number of neighbors from every batch.
    Equal distances are resolved by observation name, making the result stable
    under permutations of the input rows.

    Parameters
    ----------
    adata
        Annotated data matrix.
    batch_key
        Key in :attr:`~anndata.AnnData.obs` containing nonempty string batches.
    neighbors_within_batch
        Number of neighbors selected independently from every batch.
    use_rep
        Key in :attr:`~anndata.AnnData.obsm` containing the supplied embedding.
    metric
        Exact distance metric, either ``'euclidean'`` or ``'cosine'``.
    key_added
        Neighborhood metadata key. The default uses Scanpy's standard graph keys.
    copy
        Return a modified copy instead of changing ``adata`` in place.
    """
    if metric not in {"euclidean", "cosine"}:
        raise ValueError("metric must be either 'euclidean' or 'cosine'")
    if not isinstance(key_added, str) or not key_added:
        raise ValueError("key_added must be a nonempty string")
    if not adata.obs_names.is_unique:
        raise ValueError("observation names must be unique")
    target = adata.copy() if copy else adata
    embedding = _validate_embedding(target, use_rep)
    if metric == "cosine" and np.any(np.linalg.norm(embedding, axis=1) == 0):
        raise ValueError("cosine distance is undefined for zero-norm observations")
    batches, batch_order = _validate_batches(
        target, batch_key, neighbors_within_batch
    )
    cell_ids = target.obs_names.to_numpy(dtype=str)
    per_batch_indices, per_batch_distances = _select_neighbors(
        embedding,
        batches,
        batch_order,
        cell_ids,
        metric,
        neighbors_within_batch,
    )
    flat_indices, flat_distances = _flatten_for_graph(
        per_batch_indices, per_batch_distances, cell_ids
    )
    n_neighbors = flat_indices.shape[1]
    distances = _distance_graph(flat_indices, flat_distances, target.n_obs)
    connectivities = umap(
        flat_indices,
        flat_distances,
        n_obs=target.n_obs,
        n_neighbors=n_neighbors,
        set_op_mix_ratio=1.0,
        local_connectivity=1.0,
    )
    distances_key = "distances" if key_added == "neighbors" else f"{key_added}_distances"
    connectivities_key = (
        "connectivities"
        if key_added == "neighbors"
        else f"{key_added}_connectivities"
    )
    target.obsp[distances_key] = distances
    target.obsp[connectivities_key] = connectivities
    target.uns[key_added] = {
        "distances_key": distances_key,
        "connectivities_key": connectivities_key,
        "params": {
            "batch_key": batch_key,
            "neighbors_within_batch": int(neighbors_within_batch),
            "use_rep": use_rep,
            "metric": metric,
            "n_neighbors": n_neighbors,
            "method": "umap",
        },
        "batch_order": np.asarray(batch_order, dtype=str),
        "indices": per_batch_indices,
        "neighbor_distances": per_batch_distances,
    }
    return target if copy else None

