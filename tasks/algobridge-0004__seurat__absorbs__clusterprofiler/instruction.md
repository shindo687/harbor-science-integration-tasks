# Add native marker enrichment to Seurat

Implement a bounded over-representation analysis API directly in the locked
Seurat source tree at `/testbed`. The result must reproduce the documented
`Seurat marker table -> clusterProfiler::enricher` workflow without depending
on clusterProfiler, DOSE, qvalue, or any other enrichment package at runtime.

## Allowed source changes

Make exactly these changes:

1. add `R/enrichment.R`;
2. add exactly one `export(EnrichMarkers)` directive to `NAMESPACE`.

Do not modify or remove any other locked Seurat file. Do not add generated
artifacts, vendored packages, executables, symlinks, or test fixtures.

## Required API

```r
EnrichMarkers <- function(
  markers,
  TERM2GENE,
  universe = NULL,
  TERM2NAME = NULL,
  minGSSize = 1L,
  maxGSSize = 500L,
  pvalueCutoff = 1,
  qvalueCutoff = 1
)
```

`markers` is either a character vector of gene IDs or a standard Seurat marker
`data.frame`, in which case gene IDs are its row names. Duplicate marker IDs do
not change the result. `TERM2GENE` is a two-column data frame containing term
and gene IDs. `TERM2NAME`, when present, is a two-column term/name data frame.
All identifiers are compared as character strings.

Return a data frame with exactly these columns, in this order:

```text
term description overlap GeneRatio BgRatio pvalue p.adjust qvalue genes
```

- `overlap` is integer `k`.
- `GeneRatio` and `BgRatio` are strings `k/n` and `M/N`.
- `genes` is the lexicographically sorted hit set joined by `/`.
- rows are ordered by increasing `pvalue`, then `term`.
- no result is a zero-row data frame with the same typed columns.

## Statistical contract

Drop incomplete and duplicate TERM2GENE pairs. The annotated background is the
unique genes in TERM2GENE; a supplied `universe` is intersected with it. Let
`N` be the resulting background size. Query genes not mapped by TERM2GENE do
not contribute to `n`; `n` is the number of unique mapped query genes.

For each term hit by the query, intersect its genes with the background, let
its size be `M`, and retain it when `minGSSize <= M <= maxGSSize`. Intersect its
query hits with the background to obtain `k`. Compute the one-sided tail

```r
phyper(k - 1, M, N - M, n, lower.tail = FALSE)
```

and adjust the complete retained-term p-value family with
`p.adjust(..., method = "BH")`.

Match the locked qvalue behavior used by clusterProfiler/DOSE: estimate
`pi0 = min(1, mean(pvalue >= 0.05) / 0.95)` and form the monotone Storey
q-values `pi0 * pmin(1, cummin(p_sorted_desc * m / rank_desc))`. If `pi0 <= 0`
the q-values are `NA_real_`. Filter rows by both raw and adjusted p-value
`<= pvalueCutoff`; when no q-value is `NA`, also require
`qvalue <= qvalueCutoff`.

Reject malformed inputs and invalid bounds/cutoffs with an R error. Boundary
gene-set sizes are inclusive. A missing term name falls back to the term ID.

## Runtime and dependency rules

The implementation must be native R using only base/recommended R functions.
It may not invoke external processes, access the network, read hidden verifier
paths, dynamically load code, or import/call clusterProfiler, DOSE, the qvalue
package, or another donor implementation. The required `qvalue` output column
and `qvalueCutoff` argument are of course allowed. The verifier runs with no
network and physically deletes all donor/reference material before executing
the candidate.

Locked donor sources and five public examples are available in the Agent
environment for study. Run `/opt/task-tools/run-public-examples` to check the
current implementation. Public examples are illustrative; hidden tests cover
additional universes, duplicates, boundary sizes, filtering, extreme tails,
empty hits, malformed inputs, and mathematical invariants.
