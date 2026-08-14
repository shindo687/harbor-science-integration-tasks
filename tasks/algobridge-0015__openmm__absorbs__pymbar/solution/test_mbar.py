import importlib.util
from pathlib import Path

import numpy as np


spec = importlib.util.spec_from_file_location("oracle_mbar", Path(__file__).with_name("mbar.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_symmetric_two_state():
    result = module.estimate_mbar([[0.0, 1.0], [1.0, 0.0]], [1, 1])
    assert np.allclose(result["f_k"], 0.0)
    assert np.allclose(np.sum(result["weights"], axis=0), 1.0)
    assert np.allclose(np.sum(result["overlap"], axis=1), 1.0)


def test_common_sample_offset_invariance():
    u = np.array([[0.0, 1.0, 2.0, 3.0], [1.5, 1.0, 0.5, 0.0]])
    base = module.estimate_mbar(u, [2, 2])
    shifted = module.estimate_mbar(u + [100.0, -200.0, 700.0, -900.0], [2, 2])
    assert np.allclose(base["Delta_f"], shifted["Delta_f"], atol=1e-10)
    assert np.allclose(base["weights"], shifted["weights"], atol=1e-10)


def test_validation():
    for u, counts in [([[0.0, 1.0], [1.0, 0.0]], [1, 0]),
                      ([[0.0, None], [1.0, 0.0]], [1, 1])]:
        try:
            module.estimate_mbar(u, counts)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError("invalid input was accepted")

