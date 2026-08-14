import numpy as np

from bilby.core.sampler.internal_nested import run_nested


def test_constant_likelihood_contract():
    result = run_nested(
        lambda point: -0.4,
        lambda unit: np.asarray([-2.0 + 4.0 * unit[0]]),
        1,
        nlive=30,
        dlogz=0.1,
        seed=91,
        maxiter=300,
        walks=12,
    )
    assert abs(result.log_evidence + 0.4) < 1e-12
    assert np.isclose(result.weights.sum(), 1.0)
    assert np.all(result.weights > 0)
    assert np.all(np.diff(result.log_likelihood) >= 0)


def test_seed_is_deterministic():
    arguments = dict(nlive=35, dlogz=0.15, seed=121, maxiter=500, walks=15)
    first = run_nested(lambda x: -0.5 * x[0] ** 2, lambda u: 8 * u - 4, 1, **arguments)
    second = run_nested(lambda x: -0.5 * x[0] ** 2, lambda u: 8 * u - 4, 1, **arguments)
    np.testing.assert_array_equal(first.samples, second.samples)
    np.testing.assert_array_equal(first.weights, second.weights)

