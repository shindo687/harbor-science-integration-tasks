"""Deliberately incomplete near miss: plain prior Monte Carlo, no nesting."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math

import numpy as np
from pandas import DataFrame

from .base_sampler import Sampler


@dataclass(frozen=True)
class NestedSamplingTrace:
    iteration: int
    log_likelihood: float
    log_prior_volume: float
    log_evidence: float
    information: float
    remaining_evidence: float


@dataclass(frozen=True)
class NestedSamplingResult:
    samples: np.ndarray
    samples_u: np.ndarray
    log_likelihood: np.ndarray
    log_weights: np.ndarray
    weights: np.ndarray
    log_evidence: float
    log_evidence_err: float
    information: float
    trace: tuple
    niter: int
    ncall: int


def run_nested(loglikelihood, prior_transform, ndim, *, nlive=100, dlogz=0.1, seed=None, maxiter=None, maxcall=None, walks=25):
    if not callable(loglikelihood) or not callable(prior_transform):
        raise TypeError("callables required")
    if not isinstance(ndim, int) or ndim < 1 or ndim > 3:
        raise ValueError("invalid ndim")
    if not isinstance(nlive, int) or nlive < 2 or dlogz <= 0 or walks < 1:
        raise ValueError("invalid settings")
    if seed is not None and not isinstance(seed, int):
        raise TypeError("invalid seed")
    if maxiter is not None and maxiter < 1:
        raise ValueError("invalid maxiter")
    if maxcall is not None and maxcall < 1:
        raise ValueError("invalid maxcall")
    count = min(maxcall or 20000, max(nlive * 20, min(maxiter or 2000, 2000)))
    rng = np.random.default_rng(seed)
    unit = rng.random((count, ndim))
    samples = np.asarray([prior_transform(item) for item in unit], dtype=float)
    if samples.shape != (count, ndim) or not np.all(np.isfinite(samples)):
        raise ValueError("bad transform")
    logl = np.asarray([loglikelihood(item) for item in samples], dtype=float)
    if not np.all(np.isfinite(logl)):
        raise ValueError("bad likelihood")
    order = np.argsort(logl, kind="stable")
    samples, unit, logl = samples[order], unit[order], logl[order]
    maximum = float(np.max(logl))
    logz = maximum + math.log(float(np.mean(np.exp(logl - maximum))))
    weights = np.exp(logl - maximum)
    weights /= weights.sum()
    logweights = np.log(weights) + logz
    information = float(np.sum(weights * (logl - logz)))
    trace = tuple(
        NestedSamplingTrace(i, float(value), -float(i + 1) / count, logz, information, 0.0)
        for i, value in enumerate(logl)
    )
    return NestedSamplingResult(samples, unit, logl, logweights, weights, logz, 1 / math.sqrt(count), information, trace, count, count)


class InternalNested(Sampler):
    sampler_name = "internal_nested"
    sampling_seed_key = "seed"
    default_kwargs = {"nlive": 100, "dlogz": 0.1, "seed": None, "maxiter": None, "maxcall": None, "walks": 25}

    def __init__(self, likelihood, priors, **kwargs):
        super().__init__(likelihood=likelihood, priors=priors, skip_import_verification=True, **kwargs)

    def run_sampler(self):
        output = run_nested(self.log_likelihood, self.prior_transform, self.ndim, **self.kwargs)
        nested = DataFrame(output.samples, columns=self.search_parameter_keys)
        nested["weights"] = output.weights
        nested["log_likelihood"] = output.log_likelihood
        self.result.nested_samples = nested
        self.result.samples = output.samples
        self.result.log_likelihood_evaluations = output.log_likelihood
        self.result.log_evidence = output.log_evidence
        self.result.log_evidence_err = output.log_evidence_err
        self.result.information_gain = output.information
        self.result.num_likelihood_evaluations = output.ncall
        self.result.meta_data["internal_nested"] = {"trace": [asdict(x) for x in output.trace]}
        return self.result

