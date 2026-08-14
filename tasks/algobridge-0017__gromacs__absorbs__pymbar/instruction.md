# Implement native bounded BAR analysis in GROMACS

Work only in `/testbed`, which contains the locked GROMACS 2024.6 source tree.
Implement a new native analysis command:

```text
gmx bar-internal -f INPUT.bar -o OUTPUT.json
```

The final candidate must be independent GROMACS C++ source. It must not import,
execute, link, download, or vendor pymbar, Python, NumPy, SciPy, or another BAR
implementation. The verifier has no network and physically removes the locked
reference source/runtime before candidate execution.

## Allowed source changes

You may make exactly these changes:

- add `src/gromacs/gmxana/gmx_bar_internal.cpp`;
- edit `src/programs/legacymodules.cpp` only as needed to declare and register
  the new `bar-internal` command.

Do not modify, remove, or add any other source file. The existing
`src/gromacs/gmxana/CMakeLists.txt` discovers analysis `.cpp` files at CMake
configure time.

## Input format

`INPUT.bar` is ASCII whitespace-delimited data in this exact order:

```text
BAR_INTERNAL_V1
relative_tolerance 1e-12
maximum_iterations 1000
initial_delta_f 0.0
forward 4
0.2 0.4 0.1 0.3
reverse 3
-0.1 -0.3 -0.2
```

Requirements:

- `relative_tolerance` is finite and in `[1e-15, 1e-2]`;
- `maximum_iterations` is an integer in `[1, 100000]`;
- `initial_delta_f` is finite;
- forward and reverse each contain 1--100000 finite double values;
- no token may follow the final reverse value.

Malformed input must return a nonzero exit status and must not leave a valid
output file.

## Numerical contract

Let `N_F`, `N_R` be the sample counts and `M = log(N_F/N_R)`. Solve for
`Delta_f` such that

```text
sum_i 1 / (1 + exp(M + w_F[i] - Delta_f))
  =
sum_j 1 / (1 + exp(-M + w_R[j] + Delta_f)).
```

The implementation must remain finite for reduced works with magnitude up to
1000. Do not evaluate an overflowing exponential merely to cancel it later.
Use the converged solution to compute the asymptotic uncertainty selected by
locked `pymbar.bar(..., uncertainty_method="BAR")` and the two-state scalar
overlap selected by locked `pymbar.bar_overlap`.

Write `OUTPUT.json` with exactly these fields:

```json
{
  "delta_f": 0.0,
  "uncertainty": 0.0,
  "overlap": 0.0,
  "iterations": 1,
  "function_evaluations": 3,
  "residual": 0.0,
  "converged": true,
  "n_forward": 4,
  "n_reverse": 3
}
```

All numeric values must be finite JSON numbers. `residual` is the absolute
log-sum BAR equation residual at the reported solution. Iteration and function
evaluation counts must be positive and no larger than a small constant plus
the configured limit.

The hidden differential tolerances are `1e-9` for `delta_f`, `1e-7` for
uncertainty, and `2e-8` for overlap. Hidden tests cover equal and unequal sample
counts, high/low overlap, extreme work, a single sample per direction, warm
starts, near-zero free energy, and deterministic transformations. They also
check swap/sign antisymmetry, energy-zero invariance, replication behavior,
the BAR residual, finite outputs, malformed inputs, original GROMACS behavior,
source integrity, and absence of reference dependencies.

After implementation, run `/opt/task-tools/run-public-examples` to configure
and build modified GROMACS and replay all five public fixtures.

