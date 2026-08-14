"""Small, native static nested sampler for bounded Bilby problems.

This implementation intentionally covers only the task's one-to-three
dimensional, fixed-live-point scope. It does not depend on dynesty.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from numbers import Integral, Real

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
    trace: tuple[NestedSamplingTrace, ...]
    niter: int
    ncall: int


def _positive_integer(name, value, minimum=1):
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise TypeError(f"{name} must be an integer")
    value = int(value)
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return value


def _finite_positive(name, value):
    if isinstance(value, bool) or not isinstance(value, Real):
        raise TypeError(f"{name} must be a real number")
    value = float(value)
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
    return value


def _log_subtract(left, right):
    """Return log(exp(left) - exp(right)) for left > right."""
    return left + math.log1p(-math.exp(right - left))


def _update_evidence(logz, information, logweight, loglike):
    updated = float(np.logaddexp(logz, logweight))
    if np.isneginf(logz):
        updated_information = loglike - updated
    else:
        old_fraction = math.exp(logz - updated)
        new_fraction = math.exp(logweight - updated)
        updated_information = (
            new_fraction * loglike
            + old_fraction * (information + logz)
            - updated
        )
    return updated, max(0.0, float(updated_information))


def _reflect_unit_cube(point):
    folded = np.mod(point, 2.0)
    return np.where(folded <= 1.0, folded, 2.0 - folded)


def run_nested(
    loglikelihood,
    prior_transform,
    ndim,
    *,
    nlive=100,
    dlogz=0.1,
    seed=None,
    maxiter=None,
    maxcall=None,
    walks=25,
):
    """Run fixed-live-point nested sampling in a bounded unit cube."""
    if not callable(loglikelihood) or not callable(prior_transform):
        raise TypeError("loglikelihood and prior_transform must be callable")
    ndim = _positive_integer("ndim", ndim)
    if ndim > 3:
        raise ValueError("this bounded sampler supports at most three dimensions")
    nlive = _positive_integer("nlive", nlive, minimum=2)
    dlogz = _finite_positive("dlogz", dlogz)
    walks = _positive_integer("walks", walks)
    if seed is not None and (isinstance(seed, bool) or not isinstance(seed, Integral)):
        raise TypeError("seed must be an integer or None")
    maxiter = 10000 if maxiter is None else _positive_integer("maxiter", maxiter)
    maxcall = 1000000 if maxcall is None else _positive_integer("maxcall", maxcall)
    if maxcall < nlive:
        raise ValueError("maxcall must permit initialization of every live point")

    rng = np.random.default_rng(None if seed is None else int(seed))

    def transform(unit):
        value = np.asarray(prior_transform(np.asarray(unit, dtype=float)), dtype=float)
        if value.shape != (ndim,):
            raise ValueError(f"prior_transform must return shape ({ndim},)")
        if not np.all(np.isfinite(value)):
            raise ValueError("prior_transform returned a non-finite point")
        return value

    def evaluate(point):
        value = float(loglikelihood(np.asarray(point, dtype=float)))
        if not np.isfinite(value):
            raise ValueError("loglikelihood returned a non-finite value")
        return value

    live_u = rng.random((nlive, ndim))
    live_v = np.empty((nlive, ndim), dtype=float)
    live_logl = np.empty(nlive, dtype=float)
    for index in range(nlive):
        live_v[index] = transform(live_u[index])
        live_logl[index] = evaluate(live_v[index])
    ncall = nlive

    samples_u = []
    samples = []
    loglikes = []
    logweights = []
    trace = []
    logz = -math.inf
    information = 0.0
    log_volume = 0.0
    iteration = 0

    while iteration < maxiter and ncall < maxcall:
        # A constant live likelihood is an exact plateau: the whole remaining
        # volume can be assigned to the final live set without replacements.
        if float(np.ptp(live_logl)) == 0.0:
            break
        if np.isfinite(logz):
            remaining_logz = float(np.max(live_logl) + log_volume)
            remaining_delta = float(np.logaddexp(logz, remaining_logz) - logz)
            if remaining_delta < dlogz:
                break
        else:
            remaining_logz = float(np.max(live_logl) + log_volume)
            remaining_delta = math.inf

        worst = int(np.argmin(live_logl))
        dead_loglike = float(live_logl[worst])
        next_log_volume = -(iteration + 1.0) / nlive
        log_width = _log_subtract(log_volume, next_log_volume)
        log_weight = log_width + dead_loglike
        logz, information = _update_evidence(
            logz, information, log_weight, dead_loglike
        )
        samples_u.append(live_u[worst].copy())
        samples.append(live_v[worst].copy())
        loglikes.append(dead_loglike)
        logweights.append(log_weight)

        remaining_logz = float(np.max(live_logl) + next_log_volume)
        remaining_delta = float(np.logaddexp(logz, remaining_logz) - logz)
        trace.append(
            NestedSamplingTrace(
                iteration=iteration,
                log_likelihood=dead_loglike,
                log_prior_volume=next_log_volume,
                log_evidence=logz,
                information=information,
                remaining_evidence=remaining_delta,
            )
        )

        survivors = np.delete(np.arange(nlive), worst)
        eligible = survivors[live_logl[survivors] > dead_loglike]
        if len(eligible) == 0:
            # Defensive counterpart of the plateau check above. This can only
            # arise from exactly tied live likelihoods.
            break
        start = int(rng.choice(eligible))
        current_u = live_u[start].copy()
        current_v = live_v[start].copy()
        current_logl = float(live_logl[start])
        spread = np.std(live_u[survivors], axis=0, ddof=0)
        step = np.clip(2.0 * spread / math.sqrt(ndim), 1e-4, 0.25)
        for _ in range(walks):
            if ncall >= maxcall:
                break
            proposal_u = _reflect_unit_cube(current_u + rng.normal(size=ndim) * step)
            proposal_v = transform(proposal_u)
            proposal_logl = evaluate(proposal_v)
            ncall += 1
            if proposal_logl > dead_loglike:
                current_u = proposal_u
                current_v = proposal_v
                current_logl = proposal_logl
        live_u[worst] = current_u
        live_v[worst] = current_v
        live_logl[worst] = current_logl
        log_volume = next_log_volume
        iteration += 1

    # The final live set owns the remaining prior volume. Equal linear-volume
    # shares are the fixed-live-point quadrature limit and remain positive.
    for index in np.argsort(live_logl, kind="stable"):
        log_weight = log_volume - math.log(nlive) + float(live_logl[index])
        logz, information = _update_evidence(
            logz, information, log_weight, float(live_logl[index])
        )
        samples_u.append(live_u[index].copy())
        samples.append(live_v[index].copy())
        loglikes.append(float(live_logl[index]))
        logweights.append(log_weight)

    samples_u = np.asarray(samples_u, dtype=float)
    samples = np.asarray(samples, dtype=float)
    loglikes = np.asarray(loglikes, dtype=float)
    logweights = np.asarray(logweights, dtype=float)
    weights = np.exp(logweights - logz)
    weights /= weights.sum()
    information = max(0.0, float(np.sum(weights * (loglikes - logz))))
    error = math.sqrt(information / nlive)
    return NestedSamplingResult(
        samples=samples,
        samples_u=samples_u,
        log_likelihood=loglikes,
        log_weights=logweights,
        weights=weights,
        log_evidence=float(logz),
        log_evidence_err=float(error),
        information=information,
        trace=tuple(trace),
        niter=iteration,
        ncall=ncall,
    )


def _systematic_resample(samples, values, weights):
    positions = (np.arange(len(weights), dtype=float) + 0.5) / len(weights)
    indices = np.searchsorted(np.cumsum(weights), positions, side="left")
    return samples[indices], values[indices]


class InternalNested(Sampler):
    """Bilby adapter for :func:`run_nested`."""

    sampler_name = "internal_nested"
    sampling_seed_key = "seed"
    default_kwargs = {
        "nlive": 100,
        "dlogz": 0.1,
        "seed": None,
        "maxiter": None,
        "maxcall": None,
        "walks": 25,
    }

    def __init__(self, likelihood, priors, **kwargs):
        super().__init__(
            likelihood=likelihood,
            priors=priors,
            skip_import_verification=True,
            **kwargs,
        )

    def run_sampler(self):
        output = run_nested(
            self.log_likelihood,
            self.prior_transform,
            self.ndim,
            **self.kwargs,
        )
        keys = self.search_parameter_keys
        nested = DataFrame(output.samples, columns=keys)
        nested["weights"] = output.weights
        nested["log_likelihood"] = output.log_likelihood
        posterior, posterior_logl = _systematic_resample(
            output.samples, output.log_likelihood, output.weights
        )
        self.result.nested_samples = nested
        self.result.samples = posterior
        self.result.log_likelihood_evaluations = posterior_logl
        self.result.log_evidence = output.log_evidence
        self.result.log_evidence_err = output.log_evidence_err
        self.result.information_gain = output.information
        self.result.num_likelihood_evaluations = output.ncall
        if self.result.meta_data is None:
            self.result.meta_data = {}
        self.result.meta_data["internal_nested"] = {
            "niter": output.niter,
            "ncall": output.ncall,
            "trace": [asdict(record) for record in output.trace],
        }
        self.sampler = output
        return self.result
