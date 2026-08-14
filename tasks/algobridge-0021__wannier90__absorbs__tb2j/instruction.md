# Add native Liechtenstein exchange evaluation to Wannier90

The checkout at `/testbed` is a locked subset of the official Wannier90 source
tree. The read-only TB2J source at `/opt/donor-sources/tb2j` is supplied as
algorithm documentation. Implement the bounded downstream capability natively
in Wannier90; the final implementation must not import, execute, link, or copy
TB2J.

Add exactly this public Fortran module and entry point:

```fortran
module w90_liechtenstein_exchange
  use, intrinsic :: iso_fortran_env, only : real64
  ...
contains
  subroutine liechtenstein_exchange(h0_up, h1_up, h0_down, h1_down, nk, nz, &
                                     efermi, smearing, exchange, moments_z, &
                                     integration_emin, status)
    complex(real64), intent(in) :: h0_up(2, 2), h1_up(2, 2)
    complex(real64), intent(in) :: h0_down(2, 2), h1_down(2, 2)
    integer, intent(in) :: nk, nz
    real(real64), intent(in) :: efermi, smearing
    real(real64), intent(out) :: exchange(2, 2, nk), moments_z(2)
    real(real64), intent(out) :: integration_emin
    integer, intent(out) :: status
  end subroutine liechtenstein_exchange
end module w90_liechtenstein_exchange
```

The file must be `/testbed/src/liechtenstein_exchange.F90`. The supported scope
is deliberately fixed: two magnetic sites, one Wannier orbital per site, and a
one-dimensional periodic Hamiltonian represented by four 2x2 complex matrices.
For spin `s`,

```text
H_s(k) = H0_s + H1_s exp(i 2 pi k) + H1_s^dagger exp(-i 2 pi k).
```

`H0_s` is Hermitian. `nk` is an odd integer from 5 through 13; use the
Monkhorst-Pack points `(i - 1/2)/nk - 1/2`. `nz` ranges from 32 through 128,
`efermi` is in eV, and `smearing` is a Fermi-Dirac width from 0.005 through
0.2 eV.

Reproduce TB2J's collinear Liechtenstein magnetic-force-theorem result for the
real-space translations `R = -nk/2, ..., nk/2`, ordered along the third array
index. Return exchange values in eV, the two local signed moments, and the
lower energy bound selected for the complex contour. The reference uses TB2J's
Legendre contour and Green-function integration. Set the on-site self-pairs
`exchange(1,1,R=0)` and `exchange(2,2,R=0)` to zero. Preserve the reciprocal
pair relation `J_ij(R) = J_ji(-R)`.

Return `status=0` on success, `status=3` for a spin-degenerate/nonmagnetic
input, and another nonzero value for unsupported or numerically invalid input.
The implementation must be deterministic and invariant under a constant local
U(1) phase on each orbital and under a common energy-origin shift.

The answer may use clean-room numerical routines in the new Fortran source,
but it cannot depend on Python, TB2J, network access, hidden verifier files,
subprocesses, precomputed case answers, or foreign-function escape paths.

Five public inputs and expected JSON results are in `/public-cases`. After
adding the module, run:

```sh
/opt/task-tools/run-public-examples
```

The hidden verifier uses the same interface with different ferromagnetic and
antiferromagnetic Hamiltonians, k meshes, contour sizes, complex hopping,
gauge/energy transforms, malformed inputs, and spin degeneracy.
