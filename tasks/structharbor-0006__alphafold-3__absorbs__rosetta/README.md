# STRUCTHARBOR-0006

This Harbor task asks an agent to add one pure-Python
`interface_energy_lite.py` post-processing module to a locked AlphaFold 3 tree.
It exercises physical energy terms, bound/unbound thermodynamic decomposition,
per-residue accounting, and Cartesian forces.

The reference is deliberately two-layered: exact independent analytic formulas
define numerical correctness, while eight frozen Rosetta InterfaceAnalyzer
scalars validate only the ordering trend on rigid variants of one real
two-chain fragment.  The task neither bundles nor executes Rosetta and does not
claim to reproduce Ref2015 values.

Key files:

- `instruction.md`: complete public contract and formulas.
- `source-lock.json`: immutable source, license, image, and calibration hashes.
- `environment/`: offline AlphaFold 3 agent environment and public fixtures.
- `tests/`: isolated differential verifier and protected frozen calibration.
- `solution/`: oracle implementation used only for acceptance testing.
- `validation/`: reproducible authoring scripts and acceptance notes.
