#!/usr/bin/env python3
"""Unprivileged candidate harness; it contains no reference answers."""

from __future__ import annotations

import importlib.metadata
import inspect
import json
import math
import sys
import traceback

import numpy as np
from scipy.special import logsumexp


def build_problem(spec):
    bounds = np.asarray(spec["bounds"], dtype=float)

    def transform(unit):
        unit = np.asarray(unit, dtype=float)
        return bounds[:, 0] + unit * (bounds[:, 1] - bounds[:, 0])

    if spec["kind"] == "gaussian":
        mean = np.asarray(spec["mean"], dtype=float)
        precision = np.linalg.inv(np.asarray(spec["cov"], dtype=float))

        def loglike(point):
            delta = np.asarray(point, dtype=float) - mean
            return -0.5 * float(delta @ precision @ delta)
    elif spec["kind"] == "mixture":
        terms = [(
            math.log(item["weight"]), np.asarray(item["mean"], dtype=float),
            np.linalg.inv(np.asarray(item["cov"], dtype=float)),
        ) for item in spec["components"]]

        def loglike(point):
            point = np.asarray(point, dtype=float)
            return float(logsumexp([
                logweight - 0.5 * float((point - mean) @ precision @ (point - mean))
                for logweight, mean, precision in terms
            ]))
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


def result_fields(result):
    required = (
        "samples", "samples_u", "log_likelihood", "log_weights", "weights",
        "log_evidence", "log_evidence_err", "information", "trace", "niter", "ncall",
    )
    missing = [name for name in required if not hasattr(result, name)]
    if missing:
        raise AttributeError(f"missing result attributes: {missing}")
    samples = np.asarray(result.samples, dtype=float)
    samples_u = np.asarray(result.samples_u, dtype=float)
    logl = np.asarray(result.log_likelihood, dtype=float)
    logw = np.asarray(result.log_weights, dtype=float)
    weights = np.asarray(result.weights, dtype=float)
    if samples.ndim != 2 or samples_u.shape != samples.shape:
        raise ValueError("samples/samples_u shape mismatch")
    if any(array.shape != (len(samples),) for array in (logl, logw, weights)):
        raise ValueError("per-sample output shape mismatch")
    mean = np.sum(samples * weights[:, None], axis=0)
    centered = samples - mean
    covariance = (centered * weights[:, None]).T @ centered
    trace = list(result.trace)
    if trace and hasattr(trace[0], "__dict__"):
        first_trace = vars(trace[0])
    elif trace and isinstance(trace[0], dict):
        first_trace = trace[0]
    else:
        first_trace = {}
    return {
        "log_evidence": float(result.log_evidence),
        "log_evidence_err": float(result.log_evidence_err),
        "information": float(result.information),
        "posterior_mean": mean.tolist(), "posterior_cov": covariance.tolist(),
        "niter": int(result.niter), "ncall": int(result.ncall),
        "sample_count": len(samples), "weights_sum": float(weights.sum()),
        "weights_min": float(weights.min()),
        "dead_likelihood_monotonic": bool(np.all(np.diff(logl) >= -1e-12)),
        "all_finite": bool(
            np.all(np.isfinite(samples)) and np.all(np.isfinite(samples_u))
            and np.all(np.isfinite(logl)) and np.all(np.isfinite(logw))
            and np.all(np.isfinite(weights)) and np.isfinite(result.log_evidence)
            and np.isfinite(result.log_evidence_err) and np.isfinite(result.information)
        ),
        "unit_cube_valid": bool(np.all((samples_u >= 0.0) & (samples_u <= 1.0))),
        "trace_length": len(trace),
        "trace_keys": sorted(first_trace),
        "trace_first_log_prior_volume": first_trace.get("log_prior_volume"),
    }


def run_core(spec):
    from bilby.core.sampler.internal_nested import run_nested

    transform, loglike = build_problem(spec)
    result = run_nested(
        loglike, transform, len(spec["bounds"]), nlive=spec["nlive"],
        dlogz=spec["dlogz"], seed=spec["seed"],
        maxiter=spec.get("maxiter", 5000), maxcall=spec.get("maxcall", 300000),
        walks=spec["walks"],
    )
    return result_fields(result)


def run_workflow(spec):
    import bilby

    keys = [f"x{index}" for index in range(len(spec["bounds"]))]
    priors = bilby.core.prior.PriorDict({
        key: bilby.core.prior.Uniform(low, high, name=key)
        for key, (low, high) in zip(keys, spec["bounds"], strict=True)
    })
    mean = np.asarray(spec["mean"], dtype=float)
    precision = np.linalg.inv(np.asarray(spec["cov"], dtype=float))

    class HiddenLikelihood(bilby.Likelihood):
        def __init__(self):
            super().__init__()
            self.parameters = {key: 0.0 for key in keys}

        def log_likelihood(self, parameters=None):
            source = self.parameters if parameters is None else parameters
            point = np.asarray([source[key] for key in keys], dtype=float)
            delta = point - mean
            return -0.5 * float(delta @ precision @ delta)

        def noise_log_likelihood(self):
            return 0.0

    result = bilby.run_sampler(
        likelihood=HiddenLikelihood(), priors=priors, sampler="internal_nested",
        nlive=spec["nlive"], dlogz=spec["dlogz"], seed=spec["seed"],
        maxiter=spec.get("maxiter", 5000), maxcall=spec.get("maxcall", 300000),
        walks=spec["walks"], outdir="/tmp/candidate-home/output", label="hidden",
        save=False, plot=False, clean=True,
    )
    nested = result.nested_samples
    weights = np.asarray(nested["weights"], dtype=float)
    samples = np.asarray(nested[keys], dtype=float)
    mean_value = np.sum(samples * weights[:, None], axis=0)
    centered = samples - mean_value
    covariance = (centered * weights[:, None]).T @ centered
    integration = result.meta_data.get("internal_nested", {})
    trace = integration.get("trace", [])
    return {
        "log_evidence": float(result.log_evidence),
        "log_evidence_err": float(result.log_evidence_err),
        "information": float(result.information_gain),
        "posterior_mean": mean_value.tolist(), "posterior_cov": covariance.tolist(),
        "nested_columns": list(nested.columns),
        "posterior_columns": list(result.posterior.columns),
        "weights_sum": float(weights.sum()), "weights_min": float(weights.min()),
        "num_likelihood_evaluations": int(result.num_likelihood_evaluations),
        "trace_present": bool(result.meta_data.get("internal_nested")),
        "integration_niter": integration.get("niter"),
        "integration_ncall": integration.get("ncall"),
        "trace_first_log_prior_volume": trace[0].get("log_prior_volume") if trace else None,
        "sampler": result.sampler,
    }


def contract_checks():
    from bilby.core.sampler import IMPLEMENTED_SAMPLERS
    from bilby.core.sampler.internal_nested import InternalNested, run_nested

    signature = inspect.signature(run_nested)
    expected = ["loglikelihood", "prior_transform", "ndim", "nlive", "dlogz", "seed", "maxiter", "maxcall", "walks"]
    checks = {
        "core_signature": list(signature.parameters) == expected,
        "class_name": InternalNested.__name__ == "InternalNested",
        "registry": "internal_nested" in IMPLEMENTED_SAMPLERS,
    }
    invalid = [
        (lambda: run_nested(lambda x: 0.0, lambda u: u, 0)),
        (lambda: run_nested(lambda x: 0.0, lambda u: u, 1, nlive=1)),
        (lambda: run_nested(lambda x: 0.0, lambda u: u, 1, dlogz=0)),
        (lambda: run_nested(lambda x: 0.0, lambda u: u, 1, walks=0)),
        (lambda: run_nested(lambda x: float("nan"), lambda u: u, 1, nlive=10)),
        (lambda: run_nested(lambda x: 0.0, lambda u: [float("nan")], 1, nlive=10)),
    ]
    rejected = []
    for call in invalid:
        try:
            call()
        except (TypeError, ValueError, RuntimeError):
            rejected.append(True)
        else:
            rejected.append(False)
    checks["invalid_inputs_rejected"] = all(rejected)
    checks["invalid_count"] = len(rejected)
    return checks


def isolation_checks():
    checks = {}
    try:
        import dynesty  # noqa: F401
    except ImportError:
        checks["dynesty_not_importable"] = True
    else:
        checks["dynesty_not_importable"] = False
    checks["dynesty_distribution_absent"] = all(
        item.metadata["Name"].lower() != "dynesty" for item in importlib.metadata.distributions()
    )
    checks["no_reference_path"] = all(
        not path.startswith(("/tests", "/opt/reference", "/opt/pristine"))
        for path in sys.path
    )
    return checks


def main():
    request = json.load(sys.stdin)
    response = {
        "isolation": isolation_checks(), "contract": contract_checks(), "results": [],
    }
    for item in request["items"]:
        try:
            if item["mode"] == "core":
                value = run_core(item["spec"])
            elif item["mode"] == "workflow":
                value = run_workflow(item["spec"])
            else:
                raise ValueError(item["mode"])
            response["results"].append({"ok": True, "value": value})
        except Exception as error:
            response["results"].append({
                "ok": False, "error": f"{type(error).__name__}: {error}",
                "traceback": traceback.format_exc(limit=8),
            })
    print("@@RESULT@@" + json.dumps(response, allow_nan=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
