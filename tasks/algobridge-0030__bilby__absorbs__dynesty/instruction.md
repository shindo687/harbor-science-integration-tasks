# Task: implement Bilby's native bounded static nested sampler

The working tree at `/testbed` is the locked Bilby source at commit
`a139afa5e0bb1879f18aed28344adec8ca6cab9b`. Packaging metadata already contains
the `bilby.internal_nested` entry point so public examples can discover your
new class. Implement a clean-room, native static nested sampler named
`internal_nested` inside Bilby.

This is an algorithm-migration task. A wrapper around dynesty, a renamed
existing sampler, or precomputed answers is not an implementation.

## Research material and submission boundary

- The locked dynesty commit `d8affbcd18d1cb894e0c7102ba31c65794461b55`
  and its MIT license are available for study at `/opt/dynesty-source`.
- Five public examples are available at `/examples`. After implementing the
  interface, run `python3 /examples/verify_examples.py`.
- The environment is offline. Only `/testbed` is submitted to the separate
  verifier; `/opt/dynesty-source` never crosses that boundary.
- The final implementation must not import, execute, link, install, download,
  or vendor dynesty. It may use Bilby's existing dependencies, NumPy, SciPy,
  pandas, and the Python standard library.

## Bounded scientific scope

Implement static nested sampling for one to three continuous parameters:

- a fixed number of live points;
- prior transformation from the unit cube;
- constrained random-walk replacement of the worst live point;
- a deterministic NumPy `Generator` controlled by `seed`;
- evidence quadrature, information gain, and an evidence-error estimate;
- stopping from an upper bound on the remaining evidence;
- no dynamic batches, parallel pool, checkpoint/resume, periodic dimensions,
  or reflective dimensions.

## Core API

Add `bilby/core/sampler/internal_nested.py` with:

```python
run_nested(
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
) -> NestedSamplingResult
```

The result must expose these public attributes:

```text
samples, samples_u, log_likelihood, log_weights, weights,
log_evidence, log_evidence_err, information,
trace, niter, ncall
```

`samples` and `samples_u` contain every weighted dead/final-live sample;
`weights` are normalized posterior weights. Each `trace` record must expose at
least the iteration, dead-point log likelihood, log prior volume, cumulative
log evidence, cumulative information, and remaining-evidence bound.

Validate all inputs and reject non-finite transformed points or likelihoods.
The returned dead/final-live likelihood sequence must be nondecreasing, all
normalized weights must be finite and strictly positive, and weights must sum
to one within floating-point accuracy.

## Bilby workflow integration

Add an `InternalNested` subclass of Bilby's `Sampler`, register the
`bilby.internal_nested` entry point, and make this standard call work without
dynesty installed:

```python
bilby.run_sampler(
    likelihood=likelihood,
    priors=priors,
    sampler="internal_nested",
    nlive=100,
    dlogz=0.1,
    seed=1234,
    maxiter=2000,
    walks=25,
)
```

Populate the normal Bilby `Result`: `nested_samples` (parameter columns plus
`weights` and `log_likelihood`), posterior `samples`, `log_evidence`,
`log_evidence_err`, `information_gain`, likelihood-evaluation count, and the
iteration trace in `meta_data["internal_nested"]`. Preserve existing public
APIs and tests.

## Scoring

The separate, offline verifier computes fresh references by running the same
locked Bilby likelihood/prior through locked dynesty. It then deletes dynesty,
all reference code, expected values, and the pristine host before executing the
candidate as unprivileged UID 10001.

The 15 hidden points cover 1D analytic Gaussian, shifted/scaled priors, a 2D
correlated Gaussian, multimodal and flat likelihoods, hard prior boundaries,
reparameterization, stopping behavior, determinism, scientific invariants,
and the real Bilby string-selected workflow. Statistical results use explicit
evidence/posterior tolerances rather than requiring identical random traces.

Compilation/API failure, donor use or vendoring, modified locked files outside
the allowed integration surface, a failed source-provenance check, or broken
Bilby regression tests is a zero-score hard gate. After all hard gates pass,
the reward is the fraction of the 15 hidden points that pass.
