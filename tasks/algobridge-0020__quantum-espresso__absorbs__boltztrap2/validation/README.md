# Validation status

The verifier uses the original-A-plus-B differential design:

```text
locked QE-style bands -> unchanged locked BoltzTraP2 -> reference output
                                                        | compare
restored QE tree + one candidate Fortran module --------+
```

For every valid case, the verifier calls the unchanged locked
`BTPDOS`, `fermiintegrals`, and `calc_Onsager_coefficients` entry points twice
and requires byte-identical JSON results. Only then does it freeze `/testbed`,
hide `/tests`, the donor tree, and source archives, and execute the candidate as
UID 10001 without network access.

## Direct isolated Docker evidence

| Candidate | Public | Hidden | Invalid | Metamorphic | Reward |
|---|---:|---:|---:|---:|---:|
| clean-room Oracle | 5/5 | 15/15 | 10/10 | 2/2 | 1.0 |
| pristine QE (NOP) | source gate | — | — | — | 0.0 |
| plausible 1000 K cap | 5/5 | 13/15 | 10/10 | 2/2 | 0.8666666667 |

The near miss fails the 1600/2400 K case and the 1250 K particle-hole case,
showing that the hidden matrix distinguishes a superficially plausible
constant-temperature approximation rather than merely checking compilation.

Evidence reports are stored under `validation/evidence/`. Formal Harbor Oracle
and NOP evidence is now included; see `HARBOR_ACCEPTANCE.md` for the immutable
identifiers and checksums.

