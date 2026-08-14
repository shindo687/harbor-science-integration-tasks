# Add native voom fitting to edgeR

You are working in the locked edgeR 4.6.3 source tree at `/testbed`.
Implement the bounded voom/weighted-linear-model capability described below so
the workflow no longer invokes limma for this operation.

## Required change

Add exactly one implementation file, `R/voomFit.R`, and add exactly this export
line to `NAMESPACE`:

```r
export(voomFit)
```

The function signature must be:

```r
voomFit <- function(
  counts,
  design,
  contrast,
  lib.size = NULL,
  span = 0.5,
  norm.method = c("TMM", "RLE", "upperquartile", "none")
)
```

Use edgeR's existing normalization implementation. The new code must compute:

1. effective library sizes from `lib.size` and the selected edgeR normalization;
2. log2 counts per million with the usual voom prior count;
3. a LOWESS mean–variance trend and observation-level precision weights;
4. per-gene weighted least-squares coefficients;
5. one supplied contrast, empirical-Bayes moderated t statistics, and two-sided
   p-values for the bounded non-robust, non-trended case.

Return a list with exactly these fields and order:

```text
logCPM
weights
coefficients
contrast.coefficients
t
p.value
df.total
norm.factors
```

`logCPM` and `weights` must have the dimensions of `counts`;
`coefficients` must be genes by design columns; contrast/statistic fields must
have one value per gene; and `norm.factors` must have one value per sample.

Reject malformed inputs: non-finite/negative/non-integer counts, dimension
mismatches, rank-deficient designs, invalid contrasts, spans outside `(0, 1]`,
unsupported normalization methods, and invalid library sizes.

## Constraints

- Do not call, load, source, import, execute, or dynamically link limma or
  statmod from the new implementation.
- Do not use the network, subprocesses, hidden paths, or verifier files.
- Do not remove or modify existing edgeR files other than the one-line
  `NAMESPACE` export.
- Do not copy long source fragments from the donor implementation. Implement
  the bounded numerical method independently using base R and existing edgeR
  functions.

The donor source and documentation are available read-only under
`/opt/donor-sources/limma`; statmod's relevant source is under
`/opt/reference-dependencies/statmod`. Five public examples are under
`/public-cases`.

Run the public check with:

```bash
/opt/task-tools/run-public-examples
```

The verifier independently creates 15 hidden cases, runs the real locked
edgeR-to-limma reference before deleting all reference material, then executes
your implementation as an unprivileged user with no network.
