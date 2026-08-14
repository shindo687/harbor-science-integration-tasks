"""Hidden bounded nested-sampling problems (parameters, never answers)."""

from __future__ import annotations


def numeric_cases():
    return [
        {
            "name": "gaussian_centered_1d", "kind": "gaussian",
            "bounds": [[-6.0, 6.0]], "mean": [0.0], "cov": [[0.5625]],
            "nlive": 100, "dlogz": 0.08, "seed": 1121, "walks": 32,
        },
        {
            "name": "gaussian_shifted_1d", "kind": "gaussian",
            "bounds": [[-4.0, 6.0]], "mean": [1.25], "cov": [[0.36]],
            "nlive": 100, "dlogz": 0.08, "seed": 1129, "walks": 32,
        },
        {
            "name": "gaussian_narrow_1d", "kind": "gaussian",
            "bounds": [[-3.0, 3.0]], "mean": [-0.4], "cov": [[0.0625]],
            "nlive": 110, "dlogz": 0.07, "seed": 1151, "walks": 34,
        },
        {
            "name": "gaussian_correlated_2d", "kind": "gaussian",
            "bounds": [[-5.0, 5.0], [-5.0, 5.0]], "mean": [0.4, -0.7],
            "cov": [[0.7, 0.32], [0.32, 0.5]],
            "nlive": 150, "dlogz": 0.10, "seed": 1171, "walks": 38,
        },
        {
            "name": "gaussian_anisotropic_2d", "kind": "gaussian",
            "bounds": [[-8.0, 8.0], [-4.0, 5.0]], "mean": [-1.2, 1.4],
            "cov": [[1.4, 0.18], [0.18, 0.16]],
            "nlive": 160, "dlogz": 0.10, "seed": 1181, "walks": 40,
        },
        {
            "name": "gaussian_correlated_3d", "kind": "gaussian",
            "bounds": [[-5.0, 5.0], [-6.0, 4.0], [-4.0, 6.0]],
            "mean": [0.2, -0.8, 1.1],
            "cov": [[0.8, 0.22, -0.12], [0.22, 0.55, 0.16], [-0.12, 0.16, 0.45]],
            "nlive": 190, "dlogz": 0.12, "seed": 1201, "walks": 44,
        },
        {
            "name": "mixture_bimodal_1d", "kind": "mixture",
            "bounds": [[-6.0, 6.0]],
            "components": [
                {"weight": 0.35, "mean": [-2.0], "cov": [[0.16]]},
                {"weight": 0.65, "mean": [1.7], "cov": [[0.49]]},
            ],
            "nlive": 180, "dlogz": 0.10, "seed": 1213, "walks": 42,
        },
        {
            "name": "mixture_separated_2d", "kind": "mixture",
            "bounds": [[-6.0, 6.0], [-6.0, 6.0]],
            "components": [
                {"weight": 0.45, "mean": [-2.1, -1.4], "cov": [[0.42, 0.08], [0.08, 0.30]]},
                {"weight": 0.55, "mean": [1.8, 2.0], "cov": [[0.55, -0.12], [-0.12, 0.38]]},
            ],
            "nlive": 220, "dlogz": 0.12, "seed": 1231, "walks": 48,
        },
        {
            "name": "flat_likelihood", "kind": "flat",
            "bounds": [[-2.0, 3.0]], "constant": -0.75,
            "nlive": 90, "dlogz": 0.06, "seed": 1249, "walks": 28,
        },
        {
            "name": "hard_prior_boundary", "kind": "hard_boundary",
            "bounds": [[-3.0, 3.0]], "interval": [-0.6, 1.1], "outside": -35.0,
            "nlive": 160, "dlogz": 0.09, "seed": 1277, "walks": 38,
        },
    ]


def reparameterization_cases():
    return [
        {
            "name": "reparam_x", "kind": "gaussian", "bounds": [[-5.0, 5.0]],
            "mean": [0.3], "cov": [[0.49]], "nlive": 130, "dlogz": 0.08,
            "seed": 1301, "walks": 36,
        },
        {
            "name": "reparam_y", "kind": "gaussian", "bounds": [[-13.0, 17.0]],
            "mean": [2.9], "cov": [[4.41]], "nlive": 130, "dlogz": 0.08,
            "seed": 1301, "walks": 36,
        },
    ]


def workflow_case():
    return {
        "name": "bilby_string_selected_workflow", "kind": "gaussian",
        "bounds": [[-4.5, 5.5], [-5.0, 5.0]], "mean": [0.8, -0.45],
        "cov": [[0.62, 0.2], [0.2, 0.44]], "nlive": 150, "dlogz": 0.10,
        "seed": 1321, "walks": 40,
    }

