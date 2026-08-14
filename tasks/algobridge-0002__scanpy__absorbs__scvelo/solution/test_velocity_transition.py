import numpy as np
from scipy import sparse
from anndata import AnnData
from scanpy.tools import velocity_transition_graph


def test_velocity_transition_smoke():
    adata = AnnData(np.zeros((3, 3)))
    adata.layers["Ms"] = np.array([[0, 0, 0], [1, 0, 0], [2, 1, 0]], float)
    adata.layers["velocity"] = np.array([[1, -.2, -.8], [1, 0, -1], [0, 0, 0]], float)
    adata.obsp["distances"] = sparse.csr_matrix(([1., 1., 1., 1.], ([0, 1, 1, 2], [1, 0, 2, 1])), shape=(3, 3))
    adata.uns["neighbors"] = {"distances_key": "distances"}
    velocity_transition_graph(adata)
    assert np.allclose(abs(adata.obsp["velocity_transitions"]).sum(axis=1), 1)
    assert adata.obsp["velocity_graph"].multiply(adata.obsp["velocity_graph_neg"] != 0).nnz == 0
