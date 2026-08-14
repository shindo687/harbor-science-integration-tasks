import numpy as np
import unittest

from alphafold.common import protein
from alphafold.common import residue_constants
from normal_modes import analyze_normal_modes


CA = residue_constants.atom_order["CA"]


def make_protein(coords, b_factors=None):
    count = len(coords)
    positions = np.zeros((count, residue_constants.atom_type_num, 3))
    positions[:, CA] = coords
    mask = np.zeros((count, residue_constants.atom_type_num))
    mask[:, CA] = 1.0
    confidence = np.zeros_like(mask)
    confidence[:, CA] = 90 if b_factors is None else b_factors
    return protein.Protein(
        atom_positions=positions,
        aatype=np.zeros(count, dtype=int),
        atom_mask=mask,
        residue_index=np.arange(1, count + 1),
        chain_index=np.zeros(count, dtype=int),
        b_factors=confidence,
    )


TETRAHEDRON = np.asarray([
    [0.0, 0.0, 0.0], [5.0, 0.0, 0.0],
    [2.5, 4.330127, 0.0], [2.5, 1.443376, 4.082483],
])


class NormalModesTest(unittest.TestCase):

    def test_complete_tetrahedron_gnm(self):
        result = analyze_normal_modes(
            make_protein(TETRAHEDRON), model="gnm", cutoff=6, n_modes=3
        )
        np.testing.assert_allclose(result["eigenvalues"], [4, 4, 4], atol=1e-6)
        self.assertEqual(result["zero_mode_count"], 1)
        np.testing.assert_allclose(result["network_matrix"].sum(axis=1), 0)
        np.testing.assert_allclose(np.diag(result["cross_correlation"]), 1)

    def test_anm_translation_zero_modes(self):
        result = analyze_normal_modes(
            make_protein(TETRAHEDRON), model="anm", cutoff=6, n_modes=6
        )
        translations = np.zeros((12, 3))
        for coordinate in range(3):
            translations[coordinate::3, coordinate] = 1
        np.testing.assert_allclose(
            result["network_matrix"] @ translations, 0, atol=1e-12
        )
        self.assertEqual(result["zero_mode_count"], 6)

    def test_plddt_selection(self):
        result = analyze_normal_modes(
            make_protein(np.vstack((TETRAHEDRON, [[2.5, 2.0, 2.0]])),
                         [90, 90, 90, 90, 40]),
            plddt_threshold=70, cutoff=6, n_modes=3,
        )
        self.assertEqual(len(result["residue_mapping"]), 4)

    def test_invalid_inputs(self):
        options = [
            {"model": "pca"}, {"cutoff": 3.9}, {"gamma": 0},
            {"n_modes": 0}, {"chain_indices": []}, {"plddt_threshold": 101},
        ]
        for kwargs in options:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises((TypeError, ValueError)):
                    analyze_normal_modes(make_protein(TETRAHEDRON), **kwargs)


if __name__ == "__main__":
    unittest.main()
