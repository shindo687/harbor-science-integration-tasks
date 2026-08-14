# Implement native elastic-network modes in AlphaFold 2

Work only in `/testbed`, which contains the locked AlphaFold 2 source tree.
Add `alphafold/common/normal_modes.py` with the API below.  Preserve existing
AlphaFold behavior and do not make unrelated changes.

Your implementation must be independent AlphaFold code.  It must not import,
execute, link, download, or vendor ProDy or another elastic-network
implementation.  The final verifier has no network and physically removes the
reference runtime before candidate execution.

## Required API

```python
analyze_normal_modes(
    protein,
    *,
    model="gnm",
    chain_indices=None,
    cutoff=10.0,
    gamma=1.0,
    plddt_threshold=None,
    n_modes=5,
)
```

`protein` is an `alphafold.common.protein.Protein`.  The verifier obtains it
with the official locked `from_pdb_string` or `from_mmcif_string` parser.
`chain_indices` refers to AlphaFold's integer chain mapping and may be `None`,
one integer, or a non-empty iterable of integers.

Return a `dict` with these keys:

- `model`: lowercase `"gnm"` or `"anm"`
- `residue_mapping`: selected residues as dictionaries containing
  `source_index`, `chain_index`, `residue_index`, and `aatype`
- `network_matrix`: the GNM Kirchhoff matrix or ANM Cartesian Hessian
- `zero_mode_count`: eigenvalues strictly below `1e-6`
- `eigenvalues`: the first requested nonzero eigenvalues in ascending order
- `modes`: corresponding orthonormal eigenvector columns
- `msf`: per-residue mean-square fluctuations from the returned modes
- `cross_correlation`: normalized per-residue fluctuation correlations

## Bounded semantics

- Select residues that have a C-alpha atom, match `chain_indices`, and have
  C-alpha B-factor/pLDDT greater than or equal to `plddt_threshold` when set.
- Preserve selected residues in their original AlphaFold order.
- Require at least four selected residues, `cutoff >= 4.0`, finite
  `gamma > 0`, and positive integer `n_modes`.
- Connect every distinct C-alpha pair whose Euclidean distance is at most the
  cutoff, using constant spring strength `gamma`.
- GNM uses the scalar graph Laplacian.  ANM uses 3x3 directional spring blocks
  in a `3N x 3N` Hessian.
- Treat eigenvalues below `1e-6` as zero and return up to `n_modes` positive
  modes.  Raise `ValueError` when there is no positive mode.
- Mode variances are inverse eigenvalues.  ANM residue covariance is the trace
  of each Cartesian 3x3 covariance block.  Normalize cross-correlation so its
  diagonal is one wherever the variance is positive.
- Reject malformed input with `TypeError` or `ValueError`.

The public examples cover both GNM and ANM.  Hidden tests additionally cover
multi-chain structures, missing C-alpha atoms, pLDDT filtering, disconnected
domains, gamma scaling, degenerate eigenspaces, PDB/mmCIF parsing, and rigid
translations/rotations.

