#!/usr/bin/env python3
"""Run public fixtures against the candidate API and stored reference summaries."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from cases import build_adata, public_cases  # noqa: E402


def canonical(matrix):
    matrix = matrix.tocsr(copy=True)
    matrix.sort_indices()
    return {
        "indptr": matrix.indptr.tolist(),
        "indices": matrix.indices.tolist(),
        "data": matrix.data.tolist(),
        "shape": list(matrix.shape),
    }


def compare_matrix(actual, expected, atol):
    actual = canonical(actual)
    return (
        actual["shape"] == expected["shape"]
        and actual["indptr"] == expected["indptr"]
        and actual["indices"] == expected["indices"]
        and np.allclose(actual["data"], expected["data"], rtol=0, atol=atol)
    )


def main():
    import scanpy as sc

    expected = json.loads((Path(__file__).parent / "expected.json").read_text())
    passed = 0
    for spec in public_cases():
        adata = build_adata(spec)
        kwargs = {key: spec[key] for key in (
            "n_recurse_neighbors", "gene_subset", "use_negative_cosines"
        ) if key in spec}
        sc.tl.velocity_transition_graph(adata, **kwargs)
        reference = expected[spec["name"]]
        checks = [
            compare_matrix(adata.obsp["velocity_graph"], reference["positive"], 1e-6),
            compare_matrix(adata.obsp["velocity_graph_neg"], reference["negative"], 1e-6),
            compare_matrix(adata.obsp["velocity_transitions"], reference["transition"], 1e-6),
            np.allclose(adata.obs["velocity_confidence"], reference["confidence"], rtol=0, atol=1e-7),
        ]
        ok = all(checks)
        passed += int(ok)
        print(f"{'PASS' if ok else 'FAIL'} {spec['name']}")
    print(f"public examples: {passed}/5")
    raise SystemExit(0 if passed == 5 else 1)


if __name__ == "__main__":
    main()
