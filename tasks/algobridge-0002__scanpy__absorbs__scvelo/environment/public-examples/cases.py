"""Five small public fixtures for the Scanpy velocity-transition task."""

from __future__ import annotations

import numpy as np
from scipy import sparse


def _distance_graph(points: np.ndarray, k: int) -> sparse.csr_matrix:
    points = np.asarray(points, dtype=float)
    rows, cols, values = [], [], []
    for i in range(len(points)):
        distance = np.linalg.norm(points - points[i], axis=1)
        order = np.lexsort((np.arange(len(points)), distance))
        chosen = [j for j in order if j != i][:k]
        rows.extend([i] * len(chosen))
        cols.extend(chosen)
        values.extend(distance[chosen])
    return sparse.csr_matrix((values, (rows, cols)), shape=(len(points), len(points)))


def public_cases():
    base = np.array(
        [[0, 0, 0], [1, 0, 0], [2, 0.2, 0], [1, 1, 0], [2, 1.1, 0]],
        dtype=float,
    )
    velocity = np.array(
        [[1, -0.2, -0.8], [0.9, -0.1, -0.8], [0.3, 0.8, -1.1],
         [0.8, 0.2, -1.0], [0.0, 0.0, 0.0]],
        dtype=float,
    )
    return [
        {"name": "linear_flow", "X": base, "V": velocity, "k": 2},
        {"name": "two_hop_branch", "X": base, "V": velocity, "k": 2,
         "n_recurse_neighbors": 2},
        {"name": "negative_cosines", "X": base, "V": -velocity, "k": 3,
         "use_negative_cosines": True},
        {"name": "zero_velocity", "X": base,
         "V": np.vstack([velocity[:1], np.zeros((4, 3))]), "k": 2},
        {"name": "gene_subset", "X": np.c_[base, base[:, :2]],
         "V": np.c_[velocity, velocity[:, :2]], "k": 2,
         "gene_subset": ["g0", "g2", "g4"]},
    ]


def build_adata(spec):
    import anndata as ad

    X = np.asarray(spec["X"], dtype=np.float64)
    adata = ad.AnnData(X=np.zeros_like(X))
    adata.obs_names = [f"c{i}" for i in range(len(X))]
    adata.var_names = [f"g{i}" for i in range(X.shape[1])]
    adata.layers["Ms"] = X
    adata.layers["Mu"] = X + np.asarray(spec["V"], dtype=np.float64)
    adata.layers["velocity"] = np.asarray(spec["V"], dtype=np.float64)
    adata.obsp["distances"] = _distance_graph(X, int(spec["k"]))
    adata.uns["neighbors"] = {
        "distances_key": "distances",
        "params": {"n_neighbors": int(spec["k"])},
    }
    return adata
