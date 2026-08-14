"""Deterministic private reduced-work fixtures for ALGOBRIDGE-0017."""

from __future__ import annotations


def _case(name, forward, reverse, *, initial=0.0, tolerance=1.0e-12,
          maximum_iterations=2000):
    return {
        "name": name,
        "forward": [float(value) for value in forward],
        "reverse": [float(value) for value in reverse],
        "initial_delta_f": float(initial),
        "relative_tolerance": float(tolerance),
        "maximum_iterations": int(maximum_iterations),
    }


def hidden_cases():
    cases = [
        _case(
            "balanced_irregular_overlap",
            [0.22, -0.08, 0.47, 0.13, 0.61, -0.19, 0.34, 0.05, 0.28],
            [-0.17, 0.02, -0.52, -0.09, -0.43, 0.21, -0.31, -0.06],
            initial=0.75,
        ),
        _case(
            "unequal_population_shifted",
            [1.31, 0.74, 1.82, 1.05, 0.58, 1.47, 0.92, 1.66, 1.18, 0.43, 1.27],
            [-0.36, -1.14, -0.71, -1.43, -0.88, -0.55],
            initial=-2.0,
        ),
        _case(
            "low_overlap_same_sign",
            [8.2, 9.1, 10.4, 11.0, 12.3, 9.8, 10.7],
            [7.9, 8.8, 9.6, 10.5, 11.7, 12.1],
            initial=1.0,
        ),
        _case("one_sample_each", [3.7], [1.2], initial=-30.0),
        _case(
            "near_zero_antisymmetric",
            [-0.42, -0.21, -0.07, 0.03, 0.18, 0.37, 0.51],
            [0.42, 0.21, 0.07, -0.03, -0.18, -0.37, -0.51],
            initial=4.0,
        ),
        _case(
            "extreme_positive_free_energy",
            [895.0, 898.5, 899.75, 900.25, 901.5, 905.0],
            [-905.0, -901.5, -900.25, -899.75, -898.5, -895.0],
            initial=-900.0,
        ),
        _case(
            "extreme_mixed_tails",
            [-500.0, -12.5, -0.75, 0.0, 9.25, 510.0],
            [-490.0, -10.75, -0.25, 0.5, 11.0, 520.0],
            initial=500.0,
        ),
        _case(
            "far_warm_start",
            [-1.7, -0.8, -0.2, 0.4, 1.3, 2.1, 0.7],
            [-2.0, -1.1, -0.5, 0.1, 0.9, 1.8],
            initial=450.0,
        ),
        _case(
            "repeated_plateaus_unequal",
            [2.0, 2.0, 2.0, 2.0, 2.0, 2.0,
             2.0, 2.0, 2.0, 2.0, 1.999, 2.001],
            [-2.0, -2.0, -2.0, -2.0, -2.0, -1.999, -2.001],
            initial=0.0,
        ),
    ]

    swap_forward = [0.41, 1.16, -0.23, 0.79, 1.52]
    swap_reverse = [-0.34, -0.91, 0.12, -1.24]
    cases.extend([
        _case("swap_sign_base", swap_forward, swap_reverse, initial=0.4),
        _case(
            "swap_sign_transformed",
            swap_reverse,
            swap_forward,
            initial=-0.4,
        ),
    ])

    shift_forward = [-1.23, -0.44, 0.31, 1.08, 1.79, 0.63]
    shift_reverse = [-1.37, -0.52, 0.17, 0.94, 1.48]
    shift = 7.25
    cases.extend([
        _case("energy_zero_base", shift_forward, shift_reverse, initial=0.0),
        _case(
            "energy_zero_shifted",
            [value + shift for value in shift_forward],
            [value - shift for value in shift_reverse],
            initial=shift,
        ),
    ])

    replicate_forward = [0.24, -0.13, 0.56, 0.91, -0.38]
    replicate_reverse = [-0.29, 0.04, 0.62, -0.81]
    cases.extend([
        _case("replication_base", replicate_forward, replicate_reverse),
        _case(
            "replication_tripled",
            replicate_forward * 3,
            replicate_reverse * 3,
        ),
    ])
    assert len(cases) == 15
    return cases


def invalid_cases():
    """Malformed protocol and command-line fixtures that must be rejected."""
    return [
        {"name": "invalid_magic", "raw_input": "BAR_INTERNAL_V0\n"},
        {
            "name": "invalid_missing_tolerance_label",
            "raw_input": (
                "BAR_INTERNAL_V1\ntolerance 1e-12\nmaximum_iterations 10\n"
                "initial_delta_f 0\nforward 1\n0\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_tolerance_too_small",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance 1e-16\nmaximum_iterations 10\n"
                "initial_delta_f 0\nforward 1\n0\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_tolerance_nonfinite",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance nan\nmaximum_iterations 10\n"
                "initial_delta_f 0\nforward 1\n0\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_zero_iterations",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance 1e-12\nmaximum_iterations 0\n"
                "initial_delta_f 0\nforward 1\n0\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_fractional_iterations",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance 1e-12\nmaximum_iterations 2.5\n"
                "initial_delta_f 0\nforward 1\n0\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_nonfinite_work",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance 1e-12\nmaximum_iterations 10\n"
                "initial_delta_f 0\nforward 1\ninf\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_zero_forward_count",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance 1e-12\nmaximum_iterations 10\n"
                "initial_delta_f 0\nforward 0\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_count_mismatch",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance 1e-12\nmaximum_iterations 10\n"
                "initial_delta_f 0\nforward 2\n0\nreverse 1\n0\n"
            ),
        },
        {
            "name": "invalid_trailing_token",
            "raw_input": (
                "BAR_INTERNAL_V1\nrelative_tolerance 1e-12\nmaximum_iterations 10\n"
                "initial_delta_f 0\nforward 1\n0\nreverse 1\n0\nextra\n"
            ),
        },
        {
            "name": "invalid_unknown_cli_option",
            "raw_input": "BAR_INTERNAL_V1\n",
            "arguments": ["bar-internal", "--not-an-option"],
        },
        {
            "name": "invalid_missing_output_option",
            "raw_input": "BAR_INTERNAL_V1\n",
            "arguments": ["bar-internal", "-f", "{input}"],
        },
    ]


__all__ = ["hidden_cases", "invalid_cases"]
