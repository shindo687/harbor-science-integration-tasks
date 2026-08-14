"""Small clean-room checks for the author Oracle."""

import unittest

import numpy as np

from phonopy.harmonic.third_order import fit_fc3
from phonopy.structure.atoms import PhonopyAtoms


class ThirdOrderTests(unittest.TestCase):
    def setUp(self):
        self.cell = PhonopyAtoms(
            symbols=["Si", "O"],
            cell=[[5.1, 0.2, 0.1], [0.3, 5.7, 0.4], [0.2, 0.5, 6.3]],
            scaled_positions=[[0.07, 0.13, 0.19], [0.43, 0.37, 0.31]],
        )

    def dataset(self):
        rng = np.random.default_rng(19)
        u = rng.normal(scale=0.04, size=(24, 2, 3))
        q = u[:, 1] - u[:, 0]
        gradient = q * np.array([2.0, 3.0, 4.0]) + 0.5 * q**2 * np.array([8.0, -6.0, 5.0])
        f = np.empty_like(u)
        f[:, 0] = gradient
        f[:, 1] = -gradient
        return u, f

    def test_exact_fit_and_acoustic_sum_rule(self):
        u, f = self.dataset()
        result = fit_fc3(self.cell, u, f, is_symmetry=False)
        self.assertLess(result["residual_norm"], 1e-10)
        self.assertLess(np.max(np.abs(result["fc3"].sum(axis=0))), 1e-10)

    def test_force_reconstruction(self):
        u, f = self.dataset()
        result = fit_fc3(self.cell, u, f, is_symmetry=False)
        np.testing.assert_allclose(result["predicted_forces"], f, atol=1e-10)

    def test_rejects_shape_mismatch(self):
        u, f = self.dataset()
        with self.assertRaises(ValueError):
            fit_fc3(self.cell, u, f[:-1], is_symmetry=False)

    def test_rejects_bad_symprec(self):
        u, f = self.dataset()
        with self.assertRaises(ValueError):
            fit_fc3(self.cell, u, f, is_symmetry=False, symprec=0)


if __name__ == "__main__":
    unittest.main()
