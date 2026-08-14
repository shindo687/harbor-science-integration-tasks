# Public examples

`public-cases.rds` contains five fully visible input cases:

1. balanced two-group TMM normalization;
2. unequal depth plus composition bias;
3. no between-library normalization;
4. a continuous-covariate design with span 0.4;
5. a three-group contrast using RLE normalization.

Each case is a list with `counts`, optional `lib.size`, `design`, `contrast`,
`span`, and `norm.method`. `expected.rds` was produced at runtime by the locked
edgeR 4.6.3 to limma 3.64.3 reference chain. It is intentionally public; the
15 hidden verifier cases and their outputs are not stored here.

Inside the Agent container, inspect the cases with:

```r
cases <- readRDS("/public-cases/public-cases.rds")
str(cases, max.level = 2)
```

After implementing `R/voomFit.R`, run:

```bash
/opt/task-tools/run-public-examples
```
