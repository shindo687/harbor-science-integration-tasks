"""Small clean-room checks for the author Oracle."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

import numpy as np


PATH = Path("/testbed/python_packaging/gmxapi/src/gmxapi/analysis/anm.py")
SPEC = importlib.util.spec_from_file_location("gmxapi_analysis_anm_test", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
analyze_anm = MODULE.analyze_anm


class AnmTests(unittest.TestCase):
    def setUp(self):
        self.coordinates = np.array([
            [0.00, 0.00, 0.00],
            [0.52, 0.00, 0.00],
            [0.17, 0.61, 0.00],
            [0.11, 0.22, 0.73],
        ])

    def test_hessian_sum_rule_and_modes(self):
        result = analyze_anm(self.coordinates, cutoff_nm=1.2)
        hessian = result["hessian"]
        self.assertLess(np.max(np.abs(hessian - hessian.T)), 1e-12)
        self.assertLess(
            np.max(np.abs(hessian.reshape(4, 3, 4, 3).sum(axis=2))),
            1e-12,
        )
        self.assertEqual(result["zero_mode_count"], 6)

    def test_gamma_scaling(self):
        first = analyze_anm(self.coordinates, cutoff_nm=1.2, gamma=0.5)
        second = analyze_anm(self.coordinates, cutoff_nm=1.2, gamma=1.5)
        np.testing.assert_allclose(second["eigenvalues"],
                                   3.0 * first["eigenvalues"], atol=1e-10)
        np.testing.assert_allclose(second["msf"], first["msf"] / 3.0,
                                   atol=1e-10)

    def test_ordered_selection(self):
        coordinates = np.vstack([self.coordinates, [[5.0, 5.0, 5.0]]])
        result = analyze_anm(
            coordinates, selection=[3, 1, 0, 2], cutoff_nm=1.2
        )
        self.assertEqual(result["node_indices"].tolist(), [3, 1, 0, 2])

    def test_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            analyze_anm(self.coordinates, cutoff_nm=0.2)
        with self.assertRaises(ValueError):
            analyze_anm(self.coordinates, selection=[0, 1, 1, 2])


if __name__ == "__main__":
    unittest.main()
