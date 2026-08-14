# Add native Wilson-loop Z2 analysis to Wannier90

The checkout at `/testbed` is a locked subset of the official Wannier90 source
tree. The read-only Z2Pack source at `/opt/donor-sources/z2pack` is supplied as
algorithm documentation. Implement the bounded downstream capability natively
in Wannier90; the final implementation must not import, execute, link, or copy
Z2Pack.

Add exactly this public Fortran module and entry point:

```fortran
module w90_z2_wilson_loop
  use, intrinsic :: iso_fortran_env, only : real64
  ...
contains
  subroutine z2_wilson_loop(norb, nocc, nlines, nk, hmesh, gap_tol, &
                            wcc, gap_pos, gap_size, z2, min_gap, status)
    integer, intent(in) :: norb, nocc, nlines, nk
    complex(real64), intent(in) :: hmesh(norb, norb, nk, nlines)
    real(real64), intent(in) :: gap_tol
    real(real64), intent(out) :: wcc(nocc, nlines)
    real(real64), intent(out) :: gap_pos(nlines), gap_size(nlines)
    integer, intent(out) :: z2, status
    real(real64), intent(out) :: min_gap
  end subroutine z2_wilson_loop
end module w90_z2_wilson_loop
```

The file must be `/testbed/src/z2_wilson_loop.F90`. The supported scope is
deliberately fixed: `norb=4`, `nocc=2`, at least three transverse lines, and at
least six unique loop points. `hmesh(:,:,k,line)` is a complex Hermitian Bloch
Hamiltonian. Lines sample the half Brillouin zone from 0 to 1/2; the last two
indices contain a closed loop with the endpoint omitted.

For every line:

1. diagonalize each Hamiltonian and select the two lowest eigenstates;
2. form neighbouring occupied-subspace overlap matrices, including the final
   overlap back to the first point;
3. multiply them in loop order to obtain the Wilson loop;
4. return its two sorted eigenphases modulo one as WCC;
5. report the position and size of the largest circular WCC gap.

Across the lines, reproduce the moving-largest-gap crossing parity used for the
Z2 invariant. Report the minimum direct occupied/unoccupied gap. Return
`status=0` on success, `status=2` when that gap is not greater than `gap_tol`,
and a nonzero status for unsupported or numerically invalid input. Validate the
Kramers-pair condition at both half-zone endpoints.

The implementation must be deterministic and invariant under a constant
unitary change of orbital basis. It may use clean-room numerical routines in
the new Fortran source, but it cannot depend on Python, Z2Pack, network access,
hidden verifier files, subprocesses, or foreign-function escape paths.

Five public Hamiltonian meshes and expected JSON results are in
`/public-cases`. After adding the module, run:

```sh
/opt/task-tools/run-public-examples
```

The hidden verifier uses the same interface with different gapped models,
random constant basis rotations, small gaps, energy rescalings, malformed
inputs, and an exact gap-closing rejection case.

