# AlphaFold 3 native interface-energy-lite

Implement a bounded, clean-room protein interface energy decomposition inside
the locked AlphaFold 3 source tree.  The result is a Rosetta-style educational
subset, not a reproduction of Rosetta Ref2015.

## Deliverable

Add exactly one file:

`src/alphafold3/model/interface_energy_lite.py`

It must expose:

```python
score_interface(packet: dict) -> dict
```

The module may import only `math` and `__future__`.  Do not change or remove any
locked AlphaFold 3 file.  Do not call, import, link, download, or vendor Rosetta;
do not use subprocesses, network/file access, native FFI, dynamic imports, or
serialized executable objects.  Evaluation is offline and the candidate runs
as an unprivileged user isolated from the verifier and frozen calibration data.

## Input schema

The packet has exactly these fields:

- `name`: nonempty `[A-Za-z0-9_.-]+`, at most 80 characters.
- `atoms`: 2 through 160 atom objects.  Force requests are limited to 24 atoms.
- `group_a`, `group_b`: nonempty, unique chain-id lists.  They are disjoint and
  together cover every atom chain.
- `separation_distance`: finite value in `(0, 200]` Angstrom.
- `separation_direction`: finite, nonzero length-three vector.  Normalize it.
- `parameters`: the exact parameter object described below.
- `compute_forces`: Boolean.

Every atom has exactly:

```text
id, chain, residue, coord, sigma, epsilon, charge, sasa_radius,
donor_direction, acceptor_direction
```

`id` is unique.  `chain` and `residue` are nonempty strings.  `coord` is a
finite length-three Angstrom vector.  `sigma`, `epsilon`, and `sasa_radius` are
strictly positive; `charge` is finite.  A donor/acceptor direction is either
`null` or a finite nonzero length-three vector and must be normalized.  The
direction points from that atom toward its ideal interaction partner.

The parameter object has exactly:

```text
cutoff, switch_distance, dielectric, probe_radius, solvation_gamma,
hbond_strength, hbond_distance, hbond_width
```

All values are finite and strictly positive, and `switch_distance < cutoff`.
Reject malformed input (raising `ValueError` is sufficient).

## Exact potential

Evaluate every unordered atom pair in each state.  Let `r` be pair distance,
`sigma = (sigma_i + sigma_j)/2`, and
`epsilon = sqrt(epsilon_i * epsilon_j)`.  The switching function is

```text
S(r) = 1                                      r <= switch_distance
     = 1 - 3*x^2 + 2*x^3                     inside the switch interval
     = 0                                      r >= cutoff
x    = (r - switch_distance)/(cutoff - switch_distance)
```

The pair terms are:

```text
lj_repulsive =  4*epsilon*(sigma/r)^12*S(r)
lj_attractive = -4*epsilon*(sigma/r)^6*S(r)
coulomb = 332.06371*charge_i*charge_j/(dielectric*r)*S(r)
```

For an oriented donor `i` and acceptor `j`, let `u` point from `i` to `j`,
`cd = max(0, donor_direction_i dot u)`, and
`ca = max(0, acceptor_direction_j dot -u)`.  Its contribution is

```text
-hbond_strength
 * exp(-0.5*((r-hbond_distance)/hbond_width)^2)
 * cd^2 * ca^2 * S(r)
```

Evaluate both possible donor-to-acceptor orientations for a pair and add them.

The differentiable SASA-lite term is intentionally independent of donor data:

```text
reach_ij = sasa_radius_i + sasa_radius_j + 2*probe_radius
occlusion_i = sum(j != i) exp(-(r_ij/reach_ij)^6)
area_i = 4*pi*(sasa_radius_i + probe_radius)^2 * exp(-occlusion_i)
sasa = solvation_gamma * sum_i area_i
```

The `bound` state uses input coordinates.  Construct `unbound` by translating
every atom whose chain is in `group_b` by
`separation_distance * normalized(separation_direction)`.  Do not rotate atom
directions.  For each term, `delta = bound - unbound`; `total` is the sum of the
five terms.  All calculations use ordinary Python double precision.

## Per-residue decomposition and forces

The residue key is `"<chain>:<residue>"`, sorted lexicographically.  Assign half
of every pair energy to each endpoint residue and assign each atom's full SASA
energy to its residue.  Return bound-minus-unbound per-residue terms and total;
their sum must reproduce the global delta.

If `compute_forces` is true, return the negative Cartesian gradient of
`delta.total` with respect to every input atom coordinate, in input atom order.
The unbound coordinate is derived from the same perturbed input coordinate.
Forces are checked against an independent central difference with step `1e-4`.
If false, return `null`.

## Exact output schema

```json
{
  "bound": {"terms": {"lj_repulsive": 0, "lj_attractive": 0, "coulomb": 0, "hbond": 0, "sasa": 0}, "total": 0},
  "unbound": {"terms": {"lj_repulsive": 0, "lj_attractive": 0, "coulomb": 0, "hbond": 0, "sasa": 0}, "total": 0},
  "delta": {"terms": {"lj_repulsive": 0, "lj_attractive": 0, "coulomb": 0, "hbond": 0, "sasa": 0}, "total": 0},
  "per_residue": [{"residue": "A:1", "terms": {}, "total": 0}],
  "forces": null
}
```

The real `terms` object always contains exactly the five named terms.

## Verification

The separate verifier checks 23 public/hidden analytic fixtures, invalid input,
term and residue identities, forces at `1e-4`, common rigid-transform
invariance, group-label swap (with the direction negated), and convergence at
large separation.  It also checks the combined lite-energy ranking against
eight frozen `InterfaceAnalyzer/ref2015` results on rigid variants of the same
8ZR4 two-chain fragment, requiring Spearman correlation at least `0.98`.
Calibration is ranking-only: absolute values need not match Ref2015 and no
claim of Ref2015 numerical equivalence is made.

Run `/opt/task-tools/run-public-examples` in the task environment for schema and
identity checks on the five public fixtures.
