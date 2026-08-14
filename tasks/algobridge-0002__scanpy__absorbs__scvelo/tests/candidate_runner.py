#!/usr/bin/env python3
"""Run the merged Scanpy candidate under the public AnnData contract."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import traceback

from protocol import build_adata, collect, kwargs


def contract_checks(function):
    import numpy as np
    from scipy import sparse

    base = build_adata({
        "name": "probe", "X": [[0, 0], [1, 0], [2, 1]],
        "Mu": [[1, 0], [2, 0], [2, 1]], "V": [[1, 0], [1, 0], [0, 0]],
        "var_names": ["g0", "g1"],
        "distances": {"data": [1, 1, 1, 1], "indices": [1, 0, 2, 1],
                      "indptr": [0, 1, 3, 4], "shape": [3, 3]},
        "n_neighbors": None, "n_recurse_neighbors": 1, "gene_subset": None,
        "sqrt_transform": False, "transition_scale": 10.0,
        "use_negative_cosines": False,
    })
    probes = []
    dense = base.copy()
    dense.obsp["distances"] = dense.obsp["distances"].toarray()
    probes.append(("dense_graph", dense, {}))
    missing_layer = base.copy()
    del missing_layer.layers["velocity"]
    probes.append(("missing_velocity", missing_layer, {}))
    negative = base.copy()
    negative.obsp["distances"] = -negative.obsp["distances"]
    probes.append(("negative_distance", negative, {}))
    self_edge = base.copy()
    graph = self_edge.obsp["distances"].tolil(); graph[0, 0] = 1
    self_edge.obsp["distances"] = graph.tocsr()
    probes.append(("self_edge", self_edge, {}))
    empty_row = base.copy()
    graph = empty_row.obsp["distances"].tolil(); graph[2, :] = 0
    empty_row.obsp["distances"] = graph.tocsr()
    probes.append(("empty_row", empty_row, {}))
    nan_layer = base.copy(); nan_layer.layers["velocity"][0, 0] = np.nan
    probes.append(("nonfinite_layer", nan_layer, {}))
    probes.append(("bad_recurse", base.copy(), {"n_recurse_neighbors": 3}))
    probes.append(("bad_scale", base.copy(), {"transition_scale": 0}))
    probes.append(("bad_subset", base.copy(), {"gene_subset": [True]}))
    checks = []
    for name, adata, extra in probes:
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                function(adata, **extra)
        except (TypeError, ValueError, KeyError):
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
        from scanpy.tools import velocity_transition_graph

        module = importlib.util.find_spec(velocity_transition_graph.__module__)
        if module is None or not str(module.origin).startswith("/opt/candidate-runtime/"):
            raise RuntimeError("velocity_transition_graph is not implemented in candidate Scanpy")
        if importlib.util.find_spec("scvelo") is not None:
            raise RuntimeError("scVelo is importable in candidate runtime")
        isolation = {
            "tests_unreadable": not os.access("/tests/grader.py", os.R_OK),
            "reference_runner_removed": not Path("/opt/reference-runner").exists(),
            "reference_host_removed": not Path("/opt/reference-host").exists(),
            "reference_donor_removed": not Path("/opt/reference-donor").exists(),
            "pristine_host_removed": not Path("/opt/pristine-host").exists(),
            "wheelhouse_removed": not Path("/opt/wheels").exists(),
            "candidate_tools_removed": not Path("/opt/candidate-tools").exists(),
            "scvelo_unavailable": importlib.util.find_spec("scvelo") is None,
        }
        results = []
        for spec in payload["cases"]:
            try:
                adata = build_adata(spec)
                with contextlib.redirect_stdout(io.StringIO()):
                    returned = velocity_transition_graph(adata, **kwargs(spec))
                if returned is not None:
                    raise TypeError("copy=False must return None")
                results.append({"ok": True, "result": collect(adata, spec["name"])})
            except Exception as error:
                results.append({"ok": False, "name": spec.get("name"),
                                "error": f"{type(error).__name__}: {error}"})
        original = build_adata(payload["cases"][0])
        before = original.copy()
        copied = velocity_transition_graph(original, copy=True, **kwargs(payload["cases"][0]))
        copy_semantics = (
            copied is not None and "velocity_graph" in copied.obsp
            and "velocity_graph" not in original.obsp
            and np_equal(original.layers["Ms"], before.layers["Ms"])
        )
        response = {
            "fatal": None,
            "scanpy_file": scanpy.__file__,
            "implementation_module": module.origin,
            "results": results,
            "contract_checks": contract_checks(velocity_transition_graph),
            "copy_semantics": bool(copy_semantics),
            "isolation_checks": isolation,
        }
    except Exception as error:
        response = {"fatal": f"{type(error).__name__}: {error}",
                    "traceback": traceback.format_exc(limit=6), "results": [],
                    "contract_checks": [], "copy_semantics": False,
                    "isolation_checks": {}}
    json.dump(response, sys.stdout, allow_nan=False)


def np_equal(left, right):
    import numpy as np
    return bool(np.array_equal(np.asarray(left), np.asarray(right)))


if __name__ == "__main__":
    main()
