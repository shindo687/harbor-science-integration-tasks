import importlib.util
from pathlib import Path

import numpy as np
import pytest


SPEC = importlib.util.spec_from_file_location(
    "oracle_markov_model", Path(__file__).with_name("markov_model.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
estimate_markov_model = MODULE.estimate_markov_model


def test_two_state_analytic_model():
    result = estimate_markov_model([0, 1, 0, 1, 0, 1])
    assert result["active_set"].tolist() == [0, 1]
    np.testing.assert_allclose(result["transition_matrix"], [[0, 1], [1, 0]])
    np.testing.assert_allclose(result["stationary_distribution"], [0.5, 0.5])


def test_gapped_labels_and_sample_counts():
    result = estimate_markov_model([2, 7, 2, 7, 2], lag=2, count_mode="sample")
    assert result["active_set"].tolist() == [2]
    np.testing.assert_array_equal(result["count_matrix"], [[2]])


@pytest.mark.parametrize("kwargs", [
    {"lag": 0}, {"lag": 1.5}, {"count_mode": "effective"},
    {"reversible": 1}, {"connectivity": "all"},
])
def test_invalid_options(kwargs):
    with pytest.raises((TypeError, ValueError)):
        estimate_markov_model([0, 1, 0], **kwargs)

