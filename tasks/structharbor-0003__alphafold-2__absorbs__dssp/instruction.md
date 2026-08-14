# Add native DSSP-compatible assignment to AlphaFold 2

Implement a new module at:

```text
alphafold/common/secondary_structure.py
```

It must expose:

```python
assign_secondary_structure(
    atom_positions,
    atom_mask,
    aatype,
    residue_index,
    chain_index=None,
)
```

The inputs use AlphaFold's native encodings:

- `atom_positions`: finite array shaped `[N, 37, 3]`;
- `atom_mask`: array shaped `[N, 37]`; every residue must have N, CA, C, O;
- `aatype`: integer `[N]`, using AlphaFold's 20 standard-residue order;
- `residue_index`: integer `[N]`;
- `chain_index`: optional non-negative integer `[N]`, defaulting to one chain.

Return a dictionary containing:

- `secondary_structure`: `N` codes from `H/B/E/G/I/T/S/C`;
- `acceptor_index` and `donor_index`: integer arrays shaped `[N, 2]`;
- `acceptor_energy` and `donor_energy`: finite arrays shaped `[N, 2]`.

Partner indices are zero-based positions in the input; use `-1` and energy
`0.0` when no partner exists. Report the two most favorable backbone hydrogen
bonds in donor/acceptor order. Normalize loop/blank and DSSP's optional PPII
extension `P` to `C`.

The assignment must be a native, deterministic implementation over the input
arrays. It must account for chain breaks, virtual backbone hydrogens,
electrostatic hydrogen-bond energies, turns/helices, beta bridges/ladders, and
bends closely enough to match DSSP 4.4.11.

Only add the requested module. Do not alter or remove locked AlphaFold files.
Do not call or load DSSP, `mkdssp`, a subprocess, a dynamic library, a network
service, or copied donor code/data. The final solution may depend on NumPy but
must not depend on the donor after integration.

The task is offline. DSSP's locked source and documentation are available at
`/opt/donor-source` for study. Five public examples are available in
`/examples`; run them with:

```bash
/opt/task-tools/run-public-examples
```

The separate verifier uses additional structures and runs the original locked
`mkdssp` itself to obtain reference results. Invalid shapes, missing backbone
atoms, non-finite coordinates, unsupported residue types, negative chains,
and duplicate residue identifiers must raise an exception.

