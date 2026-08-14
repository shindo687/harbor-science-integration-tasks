# ALGOBRIDGE-0005: edgeR absorbs limma

Status: accepted with Harbor 0.20.0 on 2026-08-15.

The task asks an agent to add a bounded native `voomFit()` implementation to
the locked edgeR 4.6.3 source tree. The independent reference executes the
real locked workflow:

```text
edgeR calcNormFactors -> limma voom -> lmFit -> contrasts.fit -> eBayes
```

The candidate phase runs without limma or statmod source/package access and
without networking. It compares logCPM, observation weights, fitted
coefficients, contrast coefficients, moderated t statistics and p-values on
15 hidden count/design matrices. Five additional examples are public.

Source identity is recorded in `source-lock.json`. Formal Harbor acceptance
scores Oracle `15/15` hidden plus `5/5` public with Reward `1.0`; the NOP
negative control scores `0.0`. Full identifiers and gates are recorded in
`validation/HARBOR_ACCEPTANCE.md`.

## Run

```bash
harbor run --path . --agent oracle --job-name algobridge-0005-oracle
harbor run --path . --agent nop --job-name algobridge-0005-nop
```

The build needs Docker/Compose and enough network access to pull the pinned
`r-base` image once. Runtime networking is disabled. If the exact base image is
already present but Docker Hub metadata is temporarily unavailable, Docker's
legacy offline builder can reuse it:

```bash
DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0 harbor run \
  --path . --agent oracle --force-build
```
