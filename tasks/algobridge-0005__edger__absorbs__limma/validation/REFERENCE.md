# Locked reference validation

The reference is evaluated from unchanged, byte-locked source files rather
than from precomputed hidden answers:

```text
edgeR 4.6.3 calcNormFactors.default
  -> limma 3.64.3 voom
  -> limma 3.64.3 lmFit
  -> limma 3.64.3 contrasts.fit
  -> limma 3.64.3 eBayes
```

`tests/cases.R` deterministically constructs five public and fifteen hidden
count/design cases. `tests/reference_runner.R` evaluates the chain in a fresh
R process. A source-checkout probe and an archive-extraction replay both must
produce 20 successful case outputs before the verifier milestone is committed.

The public input and expected-output digests are recorded in
`source-lock.json`. Hidden outputs are generated in the verifier at runtime and
are never shipped to the Agent container or stored in the repository.
