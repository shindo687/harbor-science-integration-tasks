"""Native bounded RNA-velocity transition graphs for Scanpy."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

import numpy as np
from scipy import sparse

if TYPE_CHECKING:
    from anndata import AnnData


def _as_finite_layer(adata: AnnData, key: str) -> np.ndarray:
    if key not in adata.layers:
        raise KeyError(f"missing layer {key!r}")
    value = adata.layers[key]
    result = value.toarray() if sparse.issparse(value) else np.asarray(value)
    if result.shape != adata.shape or not np.issubdtype(result.dtype, np.number):
        raise ValueError(f"layer {key!r} must be numeric with shape {adata.shape}")
    result = np.asarray(result, dtype=np.float64)
    if not np.isfinite(result).all():
        raise ValueError(f"layer {key!r} must be finite")
    return result


def _distance_graph(adata: AnnData, neighbors_key: str) -> sparse.csr_matrix:
    if neighbors_key not in adata.uns:
        raise KeyError(f"missing neighbors entry {neighbors_key!r}")
    metadata = adata.uns[neighbors_key]
    key = metadata.get("distances_key", "distances")
    if key not in adata.obsp:
        raise KeyError(f"missing distance graph {key!r}")
    value = adata.obsp[key]
    if not sparse.isspmatrix_csr(value):
        raise TypeError("the fixed distance graph must be CSR")
    graph = sparse.csr_matrix(value, dtype=np.float64, copy=True)
    if graph.shape != (adata.n_obs, adata.n_obs):
        raise ValueError("distance graph shape does not match AnnData")
    if not np.isfinite(graph.data).all() or np.any(graph.data < 0):
        raise ValueError("distance graph must contain finite nonnegative values")
    if np.any(graph.diagonal() != 0):
        raise ValueError("distance graph must not contain self edges")
    graph.eliminate_zeros()
    graph.sort_indices()
    if np.any(graph.getnnz(axis=1) == 0):
        raise ValueError("every cell must have at least one fixed neighbor")
    return graph


def _select_genes(adata: AnnData, subset: Sequence[str] | Sequence[bool] | None):
    if subset is None:
        return np.ones(adata.n_vars, dtype=bool)
    values = list(subset)
    if len(values) == adata.n_vars and all(isinstance(value, (bool, np.bool_)) for value in values):
        mask = np.asarray(values, dtype=bool)
    elif all(isinstance(value, str) for value in values):
        if len(set(values)) != len(values) or not values:
            raise ValueError("gene_subset names must be nonempty and unique")
        missing = sorted(set(values) - set(adata.var_names))
        if missing:
            raise KeyError(f"unknown genes: {missing}")
        mask = np.asarray(adata.var_names.isin(values), dtype=bool)
    else:
        raise ValueError("gene_subset must be gene names or an n_vars boolean mask")
    if not mask.any():
        raise ValueError("gene_subset must select at least one gene")
    return mask


def _neighbors(graph: sparse.csr_matrix, limit: int | None) -> list[np.ndarray]:
    result = []
    for row in range(graph.shape[0]):
        start, end = graph.indptr[row], graph.indptr[row + 1]
        indices = graph.indices[start:end]
        distance = graph.data[start:end]
        order = np.lexsort((indices, distance))
        if limit is not None:
            order = order[:limit]
        result.append(np.asarray(indices[order], dtype=np.int64))
    return result


def _expanded(direct: list[np.ndarray], row: int, depth: int) -> np.ndarray:
    selected = {row}
    frontier = {row}
    for _ in range(depth):
        frontier = {int(neighbor) for item in frontier for neighbor in direct[item]} - selected
        selected.update(frontier)
    return np.asarray(sorted(selected), dtype=np.int64)


def _normalize_absolute(matrix: sparse.csr_matrix) -> sparse.csr_matrix:
    total = np.asarray(abs(matrix).sum(axis=1)).ravel()
    if np.any(total == 0):
        raise ValueError("transition kernel contains an empty row")
    weights = sparse.csr_matrix((1.0 / total)[:, None])
    return matrix.multiply(weights).tocsr()


def velocity_transition_graph(
    adata: AnnData,
    *,
    vkey: str = "velocity",
    xkey: str = "Ms",
    neighbors_key: str = "neighbors",
    n_neighbors: int | None = None,
    n_recurse_neighbors: int = 1,
    gene_subset: Sequence[str] | Sequence[bool] | None = None,
    sqrt_transform: bool = False,
    transition_scale: float = 10.0,
    use_negative_cosines: bool = False,
    copy: bool = False,
) -> AnnData | None:
    """Compute deterministic velocity cosine and transition graphs."""
    if not isinstance(n_recurse_neighbors, int) or n_recurse_neighbors not in {1, 2}:
        raise ValueError("n_recurse_neighbors must be 1 or 2")
    if n_neighbors is not None and (not isinstance(n_neighbors, int) or n_neighbors <= 0):
        raise ValueError("n_neighbors must be a positive integer or None")
    if not np.isfinite(transition_scale) or transition_scale <= 0:
        raise ValueError("transition_scale must be finite and positive")
    target = adata.copy() if copy else adata
    X = _as_finite_layer(target, xkey)
    V = _as_finite_layer(target, vkey)
    graph = _distance_graph(target, neighbors_key)
    mask = _select_genes(target, gene_subset)
    X, V = X[:, mask].astype(np.float32), V[:, mask].astype(np.float32)
    if sqrt_transform:
        V = np.sqrt(np.abs(V)) * np.sign(V)
    V = V - np.mean(V, axis=1, keepdims=True)
    direct = _neighbors(graph, n_neighbors)

    rows, cols, values = [], [], []
    for row in range(target.n_obs):
        if not np.any(V[row]):
            continue
        selected = _expanded(direct, row, n_recurse_neighbors)
        displacement = X[selected] - X[row]
        if sqrt_transform:
            displacement = np.sqrt(np.abs(displacement)) * np.sign(displacement)
        centered = displacement - np.mean(displacement, axis=1, keepdims=True)
        displacement_norm = np.sqrt(np.einsum("ij,ij->i", centered, centered))
        velocity_norm = np.sqrt(np.einsum("i,i->", V[row], V[row]))
        denominator = displacement_norm * velocity_norm
        numerator = np.einsum("ij,j->i", centered, V[row])
        cosine = np.divide(numerator, denominator,
                           out=np.zeros(len(selected), dtype=np.float32), where=denominator != 0)
        cosine = np.nan_to_num(cosine, nan=0.0, posinf=0.0, neginf=0.0)
        nonzero = cosine != 0
        rows.extend([row] * int(nonzero.sum()))
        cols.extend(selected[nonzero].tolist())
        values.extend(cosine[nonzero].tolist())

    signed = sparse.coo_matrix(
        (np.asarray(values, dtype=np.float32), (rows, cols)),
        shape=(target.n_obs, target.n_obs),
        dtype=np.float32,
    ).tocsr()
    positive = signed.copy(); positive.data = np.clip(positive.data, 0, 1); positive.eliminate_zeros()
    negative = signed.copy(); negative.data = np.clip(negative.data, -1, 0); negative.eliminate_zeros()
    confidence = np.asarray(positive.max(axis=1).toarray()).ravel()
    upper = float(np.percentile(confidence, 98))
    self_probability = np.clip(upper - confidence, 0, 1).astype(np.float32)

    kernel = positive.copy()
    kernel.setdiag(self_probability)
    kernel = np.expm1(kernel * transition_scale).tocsr()
    if use_negative_cosines:
        kernel = kernel - np.expm1(-negative * transition_scale)
    else:
        kernel = kernel + np.expm1(negative * transition_scale)
        kernel.data += 1
    transition = _normalize_absolute(kernel.tocsr())

    target.obsp[f"{vkey}_graph"] = positive
    target.obsp[f"{vkey}_graph_neg"] = negative
    target.obsp[f"{vkey}_transitions"] = transition
    target.obs[f"{vkey}_confidence"] = confidence
    target.obs[f"{vkey}_self_transition"] = self_probability
    target.uns[f"{vkey}_transition_params"] = {
        "neighbors_key": neighbors_key,
        "n_neighbors": n_neighbors,
        "n_recurse_neighbors": n_recurse_neighbors,
        "sqrt_transform": bool(sqrt_transform),
        "transition_scale": float(transition_scale),
        "use_negative_cosines": bool(use_negative_cosines),
    }
    return target if copy else None
