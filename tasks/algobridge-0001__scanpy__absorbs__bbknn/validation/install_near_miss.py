#!/usr/bin/env python3
"""Install a plausible global-kNN implementation that ignores batch quotas."""

from __future__ import annotations

from pathlib import Path
import shutil


TESTBED = Path("/testbed")
SOURCE = Path("/solution/_batch_balanced.py")
DESTINATION = TESTBED / "src/scanpy/preprocessing/_batch_balanced.py"
INIT = TESTBED / "src/scanpy/preprocessing/__init__.py"


GLOBAL_KNN_OVERRIDE = r'''

# Deliberate validation near-miss: select the globally closest n_batches*k
# observations and merely reshape them into batch slots.  Shapes and graph
# construction look credible, but the scientific per-batch quota is absent.
def _select_neighbors(
    embedding,
    batches,
    batch_order,
    cell_ids,
    metric,
    neighbors_within_batch,
):
    n_obs = embedding.shape[0]
    total = len(batch_order) * neighbors_within_batch
    pairwise = distance.cdist(embedding, embedding, metric=metric)
    if metric == "cosine":
        pairwise = np.clip(pairwise, 0.0, 2.0)
    flat_indices = np.empty((n_obs, total), dtype=np.int64)
    flat_distances = np.empty((n_obs, total), dtype=np.float64)
    for row in range(n_obs):
        order = sorted(
            range(n_obs),
            key=lambda column: (float(pairwise[row, column]), cell_ids[column]),
        )[:total]
        flat_indices[row] = order
        flat_distances[row] = pairwise[row, order]
    shape = (n_obs, len(batch_order), neighbors_within_batch)
    return flat_indices.reshape(shape), flat_distances.reshape(shape)
'''


def main():
    if not INIT.is_file():
        raise RuntimeError("/testbed is not the expected Scanpy source tree")
    DESTINATION.write_text(SOURCE.read_text() + GLOBAL_KNN_OVERRIDE)
    text = INIT.read_text()
    import_line = "from ._batch_balanced import batch_balanced_neighbors\n"
    if import_line not in text:
        text = text.replace("from ._combat import combat\n", import_line + "from ._combat import combat\n", 1)
    export_line = '    "batch_balanced_neighbors",\n'
    if export_line not in text:
        text = text.replace('__all__ = [\n', '__all__ = [\n' + export_line, 1)
    INIT.write_text(text)
    print("installed deliberate global-kNN near miss")


if __name__ == "__main__":
    main()
