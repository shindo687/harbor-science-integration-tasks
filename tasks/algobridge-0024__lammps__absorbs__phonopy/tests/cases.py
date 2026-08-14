"""Deterministic hidden case definitions for ALGOBRIDGE-0024."""

from __future__ import annotations


def _case(
    name,
    cell,
    positions,
    symbols,
    masses,
    supercell,
    qpoints,
    *,
    epsilon=0.20,
    sigma=1.0,
    cutoff=2.15,
    delta=0.004,
    redundant=False,
    noise=0.0,
    shuffle=False,
    seed=1,
):
    return {
        "name": name,
        "cell": cell,
        "scaled_positions": positions,
        "symbols": symbols,
        "masses": masses,
        "supercell": supercell,
        "qpoints": qpoints,
        "epsilon": epsilon,
        "sigma": sigma,
        "cutoff": cutoff,
        "delta": delta,
        "redundant": redundant,
        "noise": noise,
        "shuffle": shuffle,
        "seed": seed,
        "symmetrize_iterations": 5,
    }


CASES = [
    _case(
        "mono_chain_four",
        [[1.12, 0, 0], [0, 6, 0], [0, 0, 6]],
        [[0, 0, 0]], ["Ar"], [39.948], [4, 1, 1],
        [[0, 0, 0], [0.25, 0, 0], [0.5, 0, 0]], seed=101,
    ),
    _case(
        "mono_chain_five",
        [[1.16, 0, 0], [0, 6, 0], [0, 0, 6]],
        [[0, 0, 0]], ["Ar"], [39.948], [5, 1, 1],
        [[0, 0, 0], [0.2, 0, 0], [0.4, 0, 0]],
        epsilon=0.13, cutoff=2.25, seed=102,
    ),
    _case(
        "mono_chain_redundant",
        [[1.10, 0, 0], [0, 6.2, 0], [0, 0, 6.2]],
        [[0, 0, 0]], ["Ne"], [20.1797], [4, 1, 1],
        [[0, 0, 0], [0.125, 0, 0], [0.375, 0, 0]],
        epsilon=0.08, redundant=True, seed=103,
    ),
    _case(
        "mono_chain_noisy",
        [[1.14, 0, 0], [0, 6, 0], [0, 0, 6]],
        [[0, 0, 0]], ["Kr"], [83.798], [4, 1, 1],
        [[0, 0, 0], [0.25, 0, 0], [0.5, 0, 0]],
        epsilon=0.17, redundant=True, noise=2e-8, shuffle=True, seed=104,
    ),
    _case(
        "square_nine",
        [[1.12, 0, 0], [0, 1.12, 0], [0, 0, 6]],
        [[0, 0, 0]], ["Ar"], [39.948], [3, 3, 1],
        [[0, 0, 0], [1 / 3, 0, 0], [1 / 3, 1 / 3, 0], [0.5, 0.5, 0]],
        cutoff=1.66, seed=105,
    ),
    _case(
        "square_soft",
        [[1.20, 0, 0], [0, 1.20, 0], [0, 0, 6]],
        [[0, 0, 0]], ["Xe"], [131.293], [3, 3, 1],
        [[0, 0, 0], [1 / 3, 0, 0], [0, 1 / 3, 0], [1 / 3, 1 / 3, 0]],
        epsilon=0.11, cutoff=1.72, redundant=True, seed=106,
    ),
    _case(
        "simple_cubic_eight",
        [[1.12, 0, 0], [0, 1.12, 0], [0, 0, 1.12]],
        [[0, 0, 0]], ["Ar"], [39.948], [2, 2, 2],
        [[0, 0, 0], [0.5, 0, 0], [0.5, 0.5, 0], [0.5, 0.5, 0.5]],
        cutoff=1.62, delta=0.003, seed=107,
    ),
    _case(
        "simple_cubic_expanded",
        [[1.28, 0, 0], [0, 1.28, 0], [0, 0, 1.28]],
        [[0, 0, 0]], ["Kr"], [83.798], [2, 2, 2],
        [[0, 0, 0], [0.5, 0, 0], [0, 0.5, 0], [0, 0, 0.5]],
        epsilon=0.16, cutoff=1.80, redundant=True, seed=108,
    ),
    _case(
        "diatomic_chain",
        [[2.24, 0, 0], [0, 6, 0], [0, 0, 6]],
        [[0, 0, 0], [0.5, 0, 0]], ["Na", "Cl"], [22.989769, 35.45], [3, 1, 1],
        [[0, 0, 0], [1 / 6, 0, 0], [1 / 3, 0, 0], [0.5, 0, 0]],
        epsilon=0.18, cutoff=2.15, seed=109,
    ),
    _case(
        "diatomic_mass_contrast",
        [[2.30, 0, 0], [0, 6.4, 0], [0, 0, 6.4]],
        [[0, 0, 0], [0.5, 0, 0]], ["Li", "I"], [6.94, 126.90447], [3, 1, 1],
        [[0, 0, 0], [1 / 6, 0, 0], [1 / 3, 0, 0], [0.5, 0, 0]],
        epsilon=0.12, cutoff=2.2, redundant=True, noise=1e-8, seed=110,
    ),
    _case(
        "diatomic_plane",
        [[2.24, 0, 0], [0, 2.24, 0], [0, 0, 6]],
        [[0, 0, 0], [0.5, 0.5, 0]], ["Mg", "O"], [24.305, 15.999], [2, 2, 1],
        [[0, 0, 0], [0.25, 0, 0], [0.25, 0.25, 0], [0.5, 0.5, 0]],
        epsilon=0.22, cutoff=1.75, delta=0.0035, seed=111,
    ),
    _case(
        "triatomic_chain",
        [[3.36, 0, 0], [0, 6.5, 0], [0, 0, 6.5]],
        [[0, 0, 0], [1 / 3, 0, 0], [2 / 3, 0, 0]],
        ["Li", "Na", "K"], [6.94, 22.989769, 39.0983], [2, 1, 1],
        [[0, 0, 0], [1 / 6, 0, 0], [1 / 3, 0, 0], [0.5, 0, 0]],
        epsilon=0.15, cutoff=2.15, redundant=True, seed=112,
    ),
    _case(
        "compressed_imaginary",
        [[0.92, 0, 0], [0, 6, 0], [0, 0, 6]],
        [[0, 0, 0]], ["Ar"], [39.948], [5, 1, 1],
        [[0, 0, 0], [0.2, 0, 0], [0.4, 0, 0], [0.5, 0, 0]],
        epsilon=0.07, cutoff=1.8, delta=0.002, seed=113,
    ),
    _case(
        "tiny_displacement",
        [[1.12, 0, 0], [0, 6, 0], [0, 0, 6]],
        [[0, 0, 0]], ["Ne"], [20.1797], [4, 1, 1],
        [[0, 0, 0], [0.125, 0, 0], [0.5, 0, 0]],
        epsilon=0.06, cutoff=2.1, delta=0.0004, redundant=True, seed=114,
    ),
    _case(
        "shuffled_records",
        [[2.26, 0, 0], [0, 6, 0], [0, 0, 6]],
        [[0, 0, 0], [0.5, 0, 0]], ["C", "Si"], [12.011, 28.085], [3, 1, 1],
        [[0, 0, 0], [1 / 6, 0, 0], [1 / 3, 0, 0], [0.5, 0, 0]],
        epsilon=0.10, cutoff=2.16, redundant=True, shuffle=True, seed=115,
    ),
]

CASE_BY_NAME = {case["name"]: case for case in CASES}

