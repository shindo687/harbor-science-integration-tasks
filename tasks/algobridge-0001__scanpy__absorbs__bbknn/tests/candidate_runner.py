#!/usr/bin/env python3
"""Public-protocol runner installed outside verifier-private paths."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import traceback

from anndata import AnnData
import numpy as np
import pandas as pd
from scipy import sparse

from protocol import decode_embedding, encode_csr, validate_result


def run_case(function, spec):
    embedding = decode_embedding(spec)
    obs = pd.DataFrame(
        {spec["batch_key"]: spec["batches"]},
        index=pd.Index(spec["cell_ids"], dtype=str),
    )
    adata = AnnData(X=np.zeros((len(obs), 1), dtype=np.float32), obs=obs)
    adata.obsm[spec["use_rep"]] = embedding
    original = adata.copy()
    with contextlib.redirect_stdout(io.StringIO()):
        returned = function(
            adata,
            batch_key=spec["batch_key"],
            neighbors_within_batch=spec["neighbors_within_batch"],
            use_rep=spec["use_rep"],
            metric=spec["metric"],
            key_added=spec["key_added"],
            copy=spec.get("copy", False),
        )
    if spec.get("copy", False):
        if returned is None or returned is adata:
            raise ValueError("copy=True must return a distinct AnnData")
        if adata.obsp or spec["key_added"] in adata.uns:
            raise ValueError("copy=True modified the input AnnData")
        target = returned
    else:
        if returned is not None:
            raise ValueError("copy=False must return None")
        target = adata
    key = spec["key_added"]
    distances_key = "distances" if key == "neighbors" else f"{key}_distances"
    connectivities_key = "connectivities" if key == "neighbors" else f"{key}_connectivities"
    metadata = target.uns[key]
    if not sparse.isspmatrix_csr(target.obsp[distances_key]):
        raise TypeError("distance graph must be a CSR matrix")
    if not sparse.isspmatrix_csr(target.obsp[connectivities_key]):
        raise TypeError("connectivity graph must be a CSR matrix")
    result = {
        "name": spec["name"],
        "cell_ids": target.obs_names.astype(str).tolist(),
        "batch_order": np.asarray(metadata["batch_order"]).astype(str).tolist(),
        "indices": np.asarray(metadata["indices"]).tolist(),
        "neighbor_distances": np.asarray(metadata["neighbor_distances"], dtype=float).tolist(),
        "distances": encode_csr(target.obsp[distances_key]),
        "connectivities": encode_csr(target.obsp[connectivities_key]),
        "return_is_copy": bool(spec.get("copy", False)),
        "metadata_keys": {
            "distances_key": metadata.get("distances_key"),
            "connectivities_key": metadata.get("connectivities_key"),
            "params": dict(metadata.get("params", {})),
        },
    }
    validate_result(result, spec)
    return result


def contract_checks(function):
    base = AnnData(
        X=np.zeros((4, 1)),
        obs=pd.DataFrame({"batch": ["a", "a", "b", "b"]}, index=["c0", "c1", "c2", "c3"]),
    )
    base.obsm["X_pca"] = np.asarray([[1.0, 0.0], [2.0, 0.0], [1.0, 1.0], [2.0, 1.0]])
    def nonstring_batch(adata):
        adata.obs.loc[:, "batch"] = [0, 0, 1, 1]
        return function(adata, batch_key="batch")

    probes = [
        ("metric", lambda a: function(a, batch_key="batch", metric="manhattan")),
        ("quota_zero", lambda a: function(a, batch_key="batch", neighbors_within_batch=0)),
        ("quota_too_large", lambda a: function(a, batch_key="batch", neighbors_within_batch=3)),
        ("nonfinite", lambda a: (a.obsm["X_pca"].__setitem__((0, 0), np.nan), function(a, batch_key="batch"))),
        ("zero_cosine", lambda a: (a.obsm["X_pca"].__setitem__((0, slice(None)), 0), function(a, batch_key="batch", metric="cosine"))),
        ("nonstring_batch", nonstring_batch),
        ("duplicate_cell_id", lambda a: (setattr(a, "obs_names", ["x", "x", "y", "z"]), function(a, batch_key="batch"))),
    ]
    checks = []
    for name, probe in probes:
        try:
            probe(base.copy())
        except (TypeError, ValueError):
            checks.append({"name": name, "rejected": True})
        except Exception as error:
            checks.append({"name": name, "rejected": False, "wrong_error": type(error).__name__})
        else:
            checks.append({"name": name, "rejected": False})
    return checks


def main():
    payload = json.load(sys.stdin)
    try:
        sys.path.insert(0, "/opt/candidate-runtime")
        import scanpy
        from scanpy.pp import batch_balanced_neighbors

        module = importlib.util.find_spec(batch_balanced_neighbors.__module__)
        if module is None or not str(module.origin).startswith("/opt/candidate-runtime/"):
            raise RuntimeError("API is not implemented in Candidate Scanpy")
        if importlib.util.find_spec("bbknn") is not None:
            raise RuntimeError("BBKNN is importable in Candidate runtime")
        isolation = {
            "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
            "reference_runner_removed": not Path("/opt/reference-runner").exists(),
            "reference_donor_removed": not Path("/opt/reference-donor").exists(),
            "pristine_host_removed": not Path("/opt/pristine-host").exists(),
            "wheelhouse_removed": not Path("/opt/wheels").exists(),
            "candidate_tools_removed": not Path("/opt/candidate-tools").exists(),
            "bbknn_unavailable": importlib.util.find_spec("bbknn") is None,
        }
        results = []
        for case in payload["cases"]:
            try:
                results.append({"ok": True, "result": run_case(batch_balanced_neighbors, case)})
            except Exception as error:
                results.append({"ok": False, "name": case.get("name"), "error": f"{type(error).__name__}: {error}"})
        response = {
            "fatal": None,
            "scanpy_file": scanpy.__file__,
            "api_module": module.origin,
            "results": results,
            "contract_checks": contract_checks(batch_balanced_neighbors),
            "isolation_checks": isolation,
        }
    except Exception as error:
        response = {
            "fatal": f"{type(error).__name__}: {error}",
            "traceback": traceback.format_exc(limit=5),
            "results": [],
            "contract_checks": [],
            "isolation_checks": {},
        }
    json.dump(response, sys.stdout, allow_nan=False)


if __name__ == "__main__":
    main()
