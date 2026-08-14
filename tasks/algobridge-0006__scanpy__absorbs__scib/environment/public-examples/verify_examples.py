#!/usr/bin/env python3
"""Offline checker for the five frozen public examples."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scanpy.metrics import lisi_graph_score
from scipy import sparse

from public_cases import public_cases


ROOT = Path(__file__).resolve().parent


def main():
    expected = json.loads((ROOT / "expected.json").read_text())
    details = []
    for case in public_cases():
        encoded = case["distances"]
        graph = sparse.csr_matrix(
            (encoded["data"], encoded["indices"], encoded["indptr"]),
            shape=encoded["shape"],
        )
        result = lisi_graph_score(
            graph,
            case["batch_labels"],
            case["cell_type_labels"],
            n_neighbors=case["n_neighbors"],
            perplexity=case["perplexity"],
        )
        reference = expected[case["name"]]
        checks = {
            "ilisi": bool(np.allclose(result["ilisi"], reference["ilisi"], rtol=1e-6, atol=1e-6)),
            "clisi": bool(np.allclose(result["clisi"], reference["clisi"], rtol=1e-6, atol=1e-6)),
            "effective_neighbors": list(result["effective_neighbors"])
            == reference["effective_neighbors"],
            "median_ilisi": bool(np.isclose(result["median_ilisi"], reference["median_ilisi"], rtol=1e-7, atol=1e-7)),
            "median_clisi": bool(np.isclose(result["median_clisi"], reference["median_clisi"], rtol=1e-7, atol=1e-7)),
        }
        details.append(
            {"name": case["name"], "passed": all(checks.values()), "checks": checks}
        )
    report = {
        "passed": sum(item["passed"] for item in details),
        "total": len(details),
        "details": details,
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["passed"] != report["total"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
