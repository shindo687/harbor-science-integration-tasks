# Add native constant-tau transport moments to Quantum ESPRESSO

You are working in the locked Quantum ESPRESSO 7.5 source tree at `/testbed`.
Implement the bounded electronic-transport operation below so this workflow no
longer invokes BoltzTraP2.

## Required source change

Add exactly one file:

```text
PP/src/transport_moments.f90
```

It must define module `transport_moments_module` and public subroutine:

```fortran
subroutine compute_transport_moments( &
    energies_ev, velocities_mps, weights, volume_a3, mus_ev, temperatures_k, &
    spin, reference_electrons, emin_ev, emax_ev, nbins, electron_count, &
    carrier_density, l0, l1, l2, conductivity, seebeck, kappa, status)
```

Use `real64`. The array contract is:

- `energies_ev(nband,nk)`;
- `velocities_mps(3,nband,nk)`;
- `weights(nk)`, positive and summing to one;
- `mus_ev(nmu)` and `temperatures_k(nt)`;
- scalar cell volume in Å³, spin degeneracy, neutral reference electron count,
  energy-grid endpoints in eV, and bin count;
- `electron_count(nt,nmu)` and `carrier_density(nt,nmu)`;
- each tensor output has shape `(3,3,nt,nmu)`;
- `status=0` means success; malformed input must return nonzero.

Bounds are `1<=nband<=8`, `1<=nk<=128`, `1<=nmu<=9`, `1<=nt<=6`, and
`32<=nbins<=512`. All numeric inputs must be finite; temperatures, volume,
spin, and weights must be positive; all band energies must lie in the supplied
energy range.

## Numerical operation

Implement the fixed-mesh, constant-relaxation-time subset:

1. form an energy histogram and velocity-outer-product transport DOS using the
   normalized k weights;
2. integrate carrier occupation and tensor moments L0/L1/L2 over the finite-
   temperature Fermi window;
3. convert atomic units using the constants used by the locked reference;
4. derive conductivity/τ, Seebeck, and zero-current electronic κ/τ through the
   Onsager relations;
5. use a stable 3x3 pseudoinverse for rank-deficient conductivity tensors.

The locked donor reference executes unchanged
`BoltzTraP2.bandlib.BTPDOS`, `fermiintegrals`, and
`calc_Onsager_coefficients`. Its source is available read-only at
`/opt/donor-sources/boltztrap2`; use it as documentation, but implement the
bounded algorithm independently.

## Constraints

- Do not modify or remove any existing Quantum ESPRESSO file.
- Do not call, import, link, execute, or dynamically load BoltzTraP2.
- The new Fortran module must perform no file, process, network, or dynamic-
  library I/O and may use only intrinsic `iso_fortran_env` and
  `ieee_arithmetic` modules.
- Do not copy long donor source fragments or hard-code fixture outputs.
- Leave no build products in `/testbed`; the verifier compiles your one source
  file with its fixed driver.

Five public cases are under `/public-cases`. Run them with:

```bash
/opt/task-tools/run-public-examples
```

The separate offline verifier runs the real donor reference twice, freezes the
restored `/testbed` read-only, hides all tests and donor runtime, and then runs
your compiled implementation as unprivileged UID 10001 on 15 hidden cases,
10 malformed inputs, and metamorphic energy-shift/order checks.

