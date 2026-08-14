# Validation and acceptance

1. Verify immutable source, image, and wheel identities.
2. Build pristine GROMACS and run every hidden reduced-work fixture through a
   real GROMACS XVG analysis step before locked pymbar computes the reference.
3. Enforce the two-file source policy and normalized donor-fragment scan.
4. Remove pristine GROMACS, pymbar, the Python reference runner, and numerical
   packages before building and executing the candidate.
5. Check original GROMACS behavior, invalid inputs, BAR differential values,
   residual/uncertainty/overlap identities, and cross-case invariants.
6. Run direct Oracle, NOP, an algorithmic near miss, a forbidden-dependency
   control, public examples, and formal Harbor Oracle/NOP jobs.

All six stages passed on 2026-08-14:

| Check | Result |
|---|---:|
| Direct Oracle | `15/15`, reward `1.0` |
| Direct NOP | reward `0.0` |
| Equal-population near miss | reward `0.0` |
| Forbidden dependency | reward `0.0` |
| Public fixtures | `5/5` |
| Formal Harbor Oracle / NOP | `1.0` / `0.0`, zero exceptions |

`evidence/` contains the immutable reports, rewards, Harbor job/trial locks and
results, artifact manifests, and a `SHA256SUMS` manifest.
