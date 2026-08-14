## Task

Work in the FastTree source tree at `/testbed`.  Add a native bounded
progressive multiple-sequence-alignment mode, then feed that alignment into
FastTree's existing tree-building path.

The Agent image also contains read-only MAFFT source and documentation at
`/opt/mafft-source` for study.  Your submitted `/testbed` must be a standalone
FastTree implementation: it must not execute, import, dynamically link,
download, vendor, or otherwise require MAFFT at build time or runtime.

## Required command-line interface

The following command must accept an **unaligned** FASTA file:

```bash
./FastTree [-nt] -quiet -noboot \
  --align-small \
  --alignment-out ALIGNED_FASTA \
  --guide-tree-out GUIDE_NEWICK \
  --align-matrix identity|blosum62 \
  --align-gap-open FLOAT \
  --align-gap-extend FLOAT \
  INPUT_FASTA
```

- Use `-nt --align-matrix identity` for DNA.
- Use `--align-matrix blosum62` for proteins.
- Gap penalties are positive finite costs.  Hidden differential fixtures use
  the documented defaults `4.0` and `0.75`.
- The mode must support 2 through 32 records, at most 512 residues per record
  and at most 8,192 residues in total.  Record identifiers are unique ASCII
  tokens containing only letters, digits, `_`, `.`, and `-`.
- Write the multiple alignment to `ALIGNED_FASTA` in FASTA format.
- Write the deterministic rooted UPGMA guide tree to `GUIDE_NEWICK` in Newick
  format with finite, non-negative branch lengths.
- Write the ordinary final FastTree Newick tree to stdout, exactly as FastTree
  normally does for an already aligned input.
- Keep existing FastTree behavior unchanged when `--align-small` is absent.

## Algorithmic requirements

Implement the bounded algorithm inside FastTree, not as a wrapper:

1. Parse and validate unaligned FASTA while preserving every identifier and
   residue sequence.
2. Compute deterministic global affine-gap pairwise alignments/distances.
3. Build a deterministic UPGMA guide tree, including a documented tie break.
4. Recursively align profiles using sum-of-pairs scoring and affine gaps.
5. Remove all-gap columns, write the requested artifacts, and pass the result
   to FastTree's existing tree inference.

The implementation may add normal C source/header files and tests.  Place
production `.c`/`.h` files in the repository root; the verifier compiles all
root-level `.c` files together with `-lm`.  The implementation must not use a
Python/Perl/shell subprocess as the alignment implementation.

## Scientific invariants

- Removing gaps from each output row must reproduce that input sequence.
- Every alignment row must have the same width, and no column may be all gaps.
- Alignment and both trees must contain exactly the input identifiers.
- Reordering input records must preserve normalized alignment homology and
  normalized final-tree splits.
- Guide-tree branches must be finite and non-negative, and root-to-leaf
  distances must be ultrametric within tolerance.

## Differential grading

The separate, no-network verifier first computes private references using the
locked MAFFT core followed by pristine FastTree.  It then removes all runnable
MAFFT/reference assets and builds/runs only the submitted FastTree as an
unprivileged user.

There are 15 hidden cases spanning DNA/protein inputs, internal/terminal/long
indels, duplicates, tied guide distances, input permutation, and 2/3/6/16
records.  For each case it compares residue-pair column homology and the final
tree's normalized split set and branch lengths.  Compilation, isolation,
legacy FastTree behavior, and source-policy checks are hard gates.

Five public examples are available in `/examples`; run them with:

```bash
/opt/task-tools/run-public-examples
```

Do not hard-code the public examples: hidden records, lengths, alphabets, and
orderings differ.
