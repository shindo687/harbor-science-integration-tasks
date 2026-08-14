# Implement native multi-frame DSSP analysis in GROMACS

Work only in `/testbed`, which contains the locked GROMACS 2024.6 source tree.
The locked DSSP 4.4.11 source is available as read-only documentation at
`/opt/donor-source`. Implement a new native analysis command:

```text
gmx dssp-internal -f INPUT.dsspint -o OUTPUT.json
```

The final implementation must be independent GROMACS C++ source. It must not
execute, link, import, download, or vendor `mkdssp`, DSSP, Python, or another
secondary-structure implementation.

## Allowed source changes

Make exactly these changes:

- add `src/gromacs/gmxana/gmx_dssp_internal.cpp`;
- edit `src/programs/legacymodules.cpp` only to declare and register
  `gmx_dssp_internal` as `dssp-internal`.

Do not add, remove, or modify any other file. GROMACS discovers new analysis
`.cpp` files during CMake configuration.

## Input protocol

The ASCII whitespace-delimited format is:

```text
DSSP_INTERNAL_V1
energy_cutoff -0.5
residues 2
frames 1
residue A 1 _ ALA
residue A 2 _ GLY
frame 0.0
box 0 0 0
atoms 1 0.1 0.2 0.3  1 0.2 0.3 0.4  1 0.3 0.4 0.5  1 0.4 0.5 0.6
atoms 1 0.5 0.6 0.7  1 0.6 0.7 0.8  1 0.7 0.8 0.9  1 0.8 0.9 1.0
```

Coordinates are GROMACS nanometers. Each `atoms` row contains N, CA, C, O in
that order. A presence flag of `1` is followed by three coordinates; `0` has
no coordinates and represents a missing backbone atom. `box` is an
orthorhombic box in nanometers: all three values are zero for nonperiodic data,
or all are at least `0.4`. Unwrap a complete chain sequentially using the
nearest image (N from the previous C, then CA from N, C from CA, O from C).
Reset unwrapping at a chain change or incomplete residue.

Bounds and validation:

- 1--500 standard amino-acid residues with unique `(chain, number, insertion)`
  keys; chain IDs are one alphanumeric character;
- 1--64 frames and at most 10,000 frame-residue combinations;
- finite frame times and coordinates;
- `energy_cutoff` is finite and in `[-2.0, -0.1]` kcal/mol;
- no trailing token is allowed.

Malformed input or command options must return nonzero and leave no valid
output file.

## DSSP algorithm

Implement the DSSP electrostatic backbone hydrogen-bond energy, including the
standard virtual amide hydrogen, proline handling, `-9.9` lower clamp and
internal `0.001 kcal/mol` rounding. Retain each residue's two best acceptor and
donor bonds. Use the requested strict energy cutoff for bridge and helix tests.

Assign H/G/I/E/B/T/S/C, including 3/4/5-turn helices, parallel and
antiparallel beta bridges/ladders, beta-bulge joining, turns, bends, chain
breaks, missing backbone atoms, and multiple chains. The rare DSSP `P`
extension is out of scope and normalizes to C.

## Output protocol

Write JSON with exactly these top-level fields:

```json
{
  "schema": "algobridge-gromacs-dssp-result-v1",
  "energy_cutoff": -0.5,
  "residue_keys": ["A:1:", "A:2:"],
  "frames": []
}
```

Each frame has exactly:

- `time_ps`;
- `complete_backbone`, one boolean per residue;
- `secondary_structure`, one H/B/E/G/I/T/S/C character per residue;
- `acceptor_index`, `acceptor_energy`, `donor_index`, `donor_energy`, each an
  `N x 2` table. Indices are zero-based topology positions and `-1` means no
  partner. Energies reproduce locked mkdssp's observable one-decimal legacy
  rendering; internally retain millikcal precision for assignment.

Incomplete residues return C, `[-1, -1]` partner rows, and `[0, 0]` energy
rows. Output numbers must be finite. Write through a temporary file so failures
cannot leave a valid result.

## Verification

Five disclosed examples are in `/opt/public-examples`. After implementation run:

```bash
/opt/task-tools/run-public-examples
```

The separate offline verifier compiles modified GROMACS and, for every frame,
runs locked real `mkdssp 4.4.11` on the same unwrapped coordinates. It checks
exact codes, partner indices and inclusion, energies within `1e-3 kcal/mol`,
multi-frame shape, missing atoms, PBC equivalence, rigid transforms, a stricter
energy cutoff, malformed inputs, native command registration, original GROMACS
behavior, source integrity, provenance, and runtime isolation. Fifteen hidden
cases are equally weighted after hard gates.
