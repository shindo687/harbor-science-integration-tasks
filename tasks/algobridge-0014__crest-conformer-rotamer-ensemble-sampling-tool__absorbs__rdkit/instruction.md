# Add bounded ETKDG conformer initialization to CREST

Work in `/testbed`, a complete locked CREST 3.0.2 source tree. A complete
RDKit 2026.03.5 source tree is available for documentation at
`/opt/donor-source`. Implement the bounded downstream capability inside CREST;
the final solution must not invoke, import, bundle, or depend on RDKit.

Add exactly one UTF-8 Python source file:

```text
src/etkdg_init.py
```

Do not modify or remove existing CREST files. The module may import only the
standard-library `math` module plus optional `__future__` features.

## Required API

```python
embed_etkdg(packet)
```

The packet is the bounded ETKDG kernel boundary after SDF parsing and chemical
perception. It contains unsmoothed topology-derived distance bounds, atom and
stereochemistry metadata, and ensemble controls. The implementation must build
and triangle-smooth the bounds matrix, perform seeded Euclidean distance
embedding, refine distance and chirality constraints, and prune redundant
conformers. It must not return template coordinates or hard-code fixtures.

Packet schema `algobridge-crest-etkdg-bounded-v1` has:

- `atomic_numbers`: 2–192 atomic numbers; fixtures have at most 64 heavy atoms
  and are non-macrocyclic.
- `pair_bounds`: every unordered atom pair exactly once as `atoms=[i,j]`,
  `lower`, `upper`; these are unsmoothed bounds.
- `chiral_constraints`: ordered `center`, three `neighbors`, desired `sign`
  (`-1` or `1`), and positive `min_volume`.
- `prune_atoms`: distinct atom indices used for rigid-invariant distance RMSD.
- `num_confs` (1–32), deterministic `seed`, `prune_rms`, and `max_attempts`.

Distances are in angstrom. Triangle smoothing must reproduce the feasible
lower/upper metric closure. Embedding is defined only up to rigid transform and
global reflection; use the chirality constraints to select handedness.

## Return value

Return exactly:

- `conformers`: accepted coordinate arrays, each `N x 3` and finite.
- `failures`: nonnegative rejected/failed attempt count.
- `rmsd_matrix`: symmetric matrix of pair-distance RMSD on `prune_atoms`.
- `bounds`: `lower` and `upper` smoothed `N x N` matrices.
- `diagnostics`: `attempts`, `accepted`, `triangle_smoothed=True`, and
  `deterministic_seed`.

The ensemble count must be at least the locked native ETKDG count and no larger
than `num_confs`. Every accepted structure must respect the bounded metric and
stereochemical tolerances. Off-diagonal RMSD values must meet `prune_rms`.
Replaying a fixed seed and reordering `pair_bounds` must not change the result.

## Validation

Reject malformed packets by raising an exception: invalid/missing pair
coverage, duplicate or out-of-range indices, inconsistent/non-finite bounds,
bad atom numbers, malformed chirality, duplicate prune atoms, or controls
outside their documented ranges.

Five disclosed packets and locked native results are in `/examples`:

```bash
/opt/task-tools/run-public-examples
```

The separate no-network verifier calls official RDKit 2026.03.5 ETKDGv3 as a
root-only reference on fifteen more molecules. It verifies triangle smoothing,
distance-bound violation, handedness, native ensemble coverage, pruning,
determinism, source integrity, provenance, and candidate/reference isolation.
Hidden reward is the fraction passed; hard-gate failures earn zero.
