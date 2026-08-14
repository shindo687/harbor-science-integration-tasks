#!/usr/bin/env python3
"""Run locked Bilby prior transforms through locked dynesty."""

from __future__ import annotations

import json
import math
import sys

import numpy as np
from scipy.special import logsumexp

import bilby
import dynesty


def build_problem(spec):
    keys = [f"x{index}" for index in range(len(spec["bounds"]))]
    priors = bilby.core.prior.PriorDict({
        key: bilby.core.prior.Uniform(low, high, name=key)
        for key, (low, high) in zip(keys, spec["bounds"], strict=True)
    })

    def transform(unit):
        return np.asarray(priors.rescale(keys, unit), dtype=float)

    if spec["kind"] == "gaussian":
        mean = np.asarray(spec["mean"], dtype=float)
        precision = np.linalg.inv(np.asarray(spec["cov"], dtype=float))

        def loglike(point):
            delta = np.asarray(point, dtype=float) - mean
            return -0.5 * float(delta @ precision @ delta)
    elif spec["kind"] == "mixture":
        terms = []
        for component in spec["components"]:
            terms.append((
                math.log(component["weight"]),
                np.asarray(component["mean"], dtype=float),
                np.linalg.inv(np.asarray(component["cov"], dtype=float)),
            ))

        def loglike(point):
            point = np.asarray(point, dtype=float)
            values = []
            for logweight, mean, precision in terms:
                delta = point - mean
                values.append(logweight - 0.5 * float(delta @ precision @ delta))
            return float(logsumexp(values))
    elif spec["kind"] == "flat":
        def loglike(point):
            del point
            return float(spec["constant"])
    elif spec["kind"] == "hard_boundary":
        def loglike(point):
            return 0.0 if spec["interval"][0] <= point[0] <= spec["interval"][1] else float(spec["outside"])
    else:
        raise ValueError(spec["kind"])
    return transform, loglike


def summarize(spec):
    transform, loglike = build_problem(spec)
    sampler = dynesty.NestedSampler(
        loglike, transform, len(spec["bounds"]), nlive=spec["nlive"],
        bound="none", sample="rwalk", walks=spec["walks"],
        rstate=np.random.default_rng(spec["seed"]),
    )
    sampler.run_nested(
        dlogz=spec["dlogz"], maxiter=spec.get("maxiter", 5000),
        maxcall=spec.get("maxcall", 300000), print_progress=False,
    )
    result = sampler.results
    samples = np.asarray(result.samples, dtype=float)
    weights = np.exp(np.asarray(result.logwt) - float(result.logz[-1]))
    weights /= weights.sum()
    mean = np.sum(samples * weights[:, None], axis=0)
    centered = samples - mean
    covariance = (centered * weights[:, None]).T @ centered
    return {
        "name": spec["name"], "log_evidence": float(result.logz[-1]),
        "log_evidence_err": float(result.logzerr[-1]),
        "information": float(result.information[-1]),
        "posterior_mean": mean.tolist(), "posterior_cov": covariance.tolist(),
        "niter": int(result.niter), "ncall": int(np.sum(result.ncall)),
    }


def main():
    request = json.load(sys.stdin)
    output = {
        "provenance": {
            "bilby_version": bilby.__version__, "bilby_file": bilby.__file__,
            "dynesty_version": dynesty.__version__, "dynesty_file": dynesty.__file__,
        },
        "results": [summarize(spec) for spec in request["cases"]],
    }
    print("@@RESULT@@" + json.dumps(output, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()

