#!/usr/bin/env python3
"""Run five public statistical checks against the candidate core API."""

from __future__ import annotations

import pathlib
import sys

import numpy as np

HERE = pathlib.Path(__file__).resolve().parent


def main():
    checkout = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed").resolve()
    sys.path.insert(0, str(checkout))
    sys.path.insert(0, str(HERE))

    from bilby.core.sampler.internal_nested import run_nested
    from public_cases import CASES, load_case

    failures = []
    for index, name in enumerate(CASES):
        transform, loglike, ndim, expected = load_case(name)
        result = run_nested(
            loglike,
            transform,
            ndim,
            nlive=90 if ndim == 1 else 140,
            dlogz=0.08,
            seed=7300 + index,
            maxiter=3500,
            maxcall=180000,
            walks=30,
        )
        samples = np.asarray(result.samples, dtype=float)
        weights = np.asarray(result.weights, dtype=float)
        mean = np.sum(samples * weights[:, None], axis=0)
        # Discontinuous plateau likelihoods have larger O(1/sqrt(nlive))
        # shrinkage variance than smooth examples at this public run size.
        logz_tol = 0.32 if name != "hard_boundary" else 0.70
        mean_tol = 0.22 if ndim == 1 else 0.30
        ok = (
            samples.ndim == 2
            and samples.shape[1] == ndim
            and np.isfinite(result.log_evidence)
            and np.isfinite(result.log_evidence_err)
            and np.isfinite(result.information)
            and np.all(weights > 0)
            and np.isclose(weights.sum(), 1.0, atol=1e-10)
            and np.all(np.diff(np.asarray(result.log_likelihood)) >= -1e-12)
            and abs(float(result.log_evidence) - expected["logz"]) <= logz_tol
            and np.max(np.abs(mean - expected["mean"])) <= mean_tol
        )
        print(
            f"{name}: {'PASS' if ok else 'FAIL'} "
            f"logZ={result.log_evidence:.5f} mean={mean.tolist()}"
        )
        if not ok:
            failures.append(name)
    if failures:
        raise SystemExit(f"failed public examples: {', '.join(failures)}")
    print(f"public examples: {len(CASES)}/{len(CASES)}")


if __name__ == "__main__":
    main()
