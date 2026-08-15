# Frozen Rosetta ranking calibration

This file documents the authoring-only materialization of
`tests/rosetta-calibration.json`.  None of these commands or licensed Rosetta
artifacts are present in either formal task image.

1. Start from PDB 8ZR4, SHA-256
   `a654d00f9f898331a6f189283813a3fdccd652f2c51093e4fc457f462db02136`
   (the exact value is also embedded in the JSON).
2. Among chains H and A, find the minimum C-alpha distance.  Its residue pair is
   H112/A266.  Retain each residue and its three sequence neighbors on both
   sides: H109-115 and A263-269, preserving all 111 `ATOM` records.
3. Find all cross-chain atom pairs within 6 Angstrom in that fragment.  The unit
   vector from the H-side pair-weighted centroid to the A-side centroid is
   `(0.853619127452, -0.284546865078, 0.436311204099)`.
4. Translate chain A along that vector by
   `[-1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 4.0]` Angstrom and write coordinates
   at PDB precision.
5. For every variant run the locally licensed application with:

   ```text
   InterfaceAnalyzer -database <licensed-database> -s <variant.pdb>
     -interface H_A -score:weights ref2015
     -pack_input false -pack_separated false -compute_packstat false
     -tracer_data_print false -overwrite -run:constant_seed -run:jran 80616
     -ignore_unrecognized_res true -load_PDB_components false
   ```

6. `build_rosetta_calibration.py` converts those PDB/score files to the frozen
   JSON using generic, independently specified atom parameters.  The resulting
   file has SHA-256
   `62ff9398f15dd2ac3ed0b41efeeeb99676c686e261e94791051b57eb21cacd2f`.

The reference installation was Rosetta
`2025.03+release.1f5080a079`; the exact InterfaceAnalyzer executable hash was
`723b3ba5a969708c1a32b877ab56e94ebb34cba587c18ba0cf2e45a695cb6857`.
Its executable, shared libraries, database, source, and parameter files are not
redistributed.  Calibration checks ordering only, never absolute equivalence.
