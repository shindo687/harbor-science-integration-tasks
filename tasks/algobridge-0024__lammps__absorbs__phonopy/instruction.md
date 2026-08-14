## Task

Work in the locked LAMMPS source tree at `/testbed`. Add a native command that
reconstructs harmonic second-order force constants from finite-displacement
force records and evaluates phonons, without using phonopy at runtime.

You may add only these files:

```text
src/fit_harmonic_fc2.cpp
src/fit_harmonic_fc2.h
```

Register this LAMMPS input command:

```text
fit_harmonic_fc2 INPUT.json OUTPUT.json
```

The command is a serial post-processing command and may run before a simulation
box is created. It must read the complete input, validate it, reconstruct and
symmetrize the full supercell FC2 tensor, construct mass-normalized dynamical
matrices at every requested q point, diagonalize them, and write the output.

## Locked JSON contract

`INPUT.json` uses `format = "algobridge-fc2-v1"` and contains:

- positive `frequency_factor` and integer `symmetrize_iterations`;
- `supercell.n_atoms`, positive `masses`, `p2s_map`, and `phase_links`;
- finite-displacement `records`, each with a displaced `atom`, a Cartesian
  three-vector `displacement`, and an `n_atoms x 3` force-response array;
- one or more finite fractional `qpoints`.

For every displaced atom, the displacement design must have rank three. The
records are force responses relative to the undisplaced LAMMPS configuration,
so the harmonic convention is `F = -Phi u`.

Each `phase_links[i][j]` entry contains the supercell atoms associated with
primitive atom `j` and their shortest-vector multiplicity/vector data relative
to primitive atom `i`. This explicit atom mapping is part of the task input; use
it to reproduce the locked phonopy phase convention.

`OUTPUT.json` must use `format = "algobridge-fc2-result-v1"` and contain:

```text
force_constants      n_atoms x n_atoms x 3 x 3
fit_residual_rms      non-negative scalar
asr_max               maximum absolute acoustic-sum-rule residual
permutation_max       maximum |Phi_ij - Phi_ji^T|
qpoint_results        one entry per input q point
```

Each q-point entry contains `qpoint`, `dynamical_matrix_real`,
`dynamical_matrix_imag`, ascending `eigenvalues`, signed `frequencies`, and
complex eigenvectors as `eigenvectors_real` and `eigenvectors_imag`. Eigenvectors
are stored by columns. Frequencies are
`sign(lambda) * sqrt(abs(lambda)) * frequency_factor`, preserving imaginary
modes as negative numbers.

## Bounded numerical contract

- 1--4 primitive atoms and 1--16 supercell atoms;
- 3--12 displacement records per displaced atom, all finite;
- displacement norm in `(0, 0.05]` and full-rank design per atom;
- 1--8 q points, each with three finite components;
- positive finite masses and frequency factor;
- `1 <= symmetrize_iterations <= 8`;
- full FC2 reconstruction uses the least-squares/pseudoinverse solution;
- each symmetrization iteration applies both translational invariance and
  permutation symmetry, followed by a final translational projection;
- the dynamical matrix is explicitly Hermitianized before diagonalization.

Reject malformed, non-finite, out-of-range, rank-deficient, or inconsistent
inputs with a non-zero LAMMPS error. Do not emit a partial output file.

## Differential verification

The private verifier runs locked pristine LAMMPS
`9e42b6f0f2c68a092d5847d4127a053dc50e126a` to generate real force responses
for displaced periodic cells. Locked phonopy
`4bac506220d426784020ea24812c93e2a016be18` then performs the original
LAMMPS-to-phonopy workflow. Only afterward does the verifier remove both
reference runtimes and run the modified LAMMPS.

It compares FC2, dynamical matrices, signed frequencies, eigenspaces for
degenerate modes, fit diagnostics, and at least these invariants:

- `Phi_ij = Phi_ji^T` and both acoustic-sum-rule axes have zero drift;
- Gamma has the expected rigid-translation acoustic subspace;
- atom reordering, record reordering, and global coordinate rotation preserve
  the appropriately aligned result;
- force scaling scales FC2/eigenvalues linearly and frequencies by the signed
  square-root law;
- non-Gamma phases change dispersive modes and imaginary modes keep their sign.

Do not import/call/link/vendor phonopy, NumPy, SciPy, another phonon solver, or
launch subprocesses. The candidate runs with no network and no donor runtime.

