# ALGOBRIDGE-0004: Seurat absorbs clusterProfiler

An accepted Harbor single-step task in which an Agent adds native marker-set
over-representation analysis to Seurat. The candidate reproduces a locked real
`Seurat marker table -> clusterProfiler::enricher` workflow, then runs with all
clusterProfiler, DOSE, and qvalue reference material physically absent.

## Capability to implement

The Agent may make exactly two source changes:

```text
add    R/enrichment.R
modify NAMESPACE (one export directive only)
```

The new `EnrichMarkers` API accepts a character marker set or standard Seurat
marker data frame, TERM2GENE, an optional universe/TERM2NAME, inclusive set-size
bounds, and p/q cutoffs. It computes the one-sided hypergeometric tail,
Benjamini-Hochberg adjustment, the locked single-lambda Storey q-value rule,
canonical hit sets, and stable empty results. See [instruction.md](instruction.md)
for the exact contract.

## Locked inputs

| Component | Lock |
|---|---|
| Seurat host | 5.3.1, commit `ca0ab0f9dd6863fac4a6af87280d48c8f9cc9b95` |
| clusterProfiler donor | 4.16.0, commit `0f8dd3d779918e9fbcdd42aa726f634fa93a6a03` |
| DOSE reference dependency | 4.2.0, commit `eb8781d71676625aaca21d072968531335a39ab0` |
| qvalue reference dependency | 2.40.0, commit `09da9f467ca4d8bddd2dbe82ba12401fcbbb2a65` |
| Runtime | R 4.5.1, `r-base` linux/amd64 image digest `a5845a19…` |

The repository includes complete deterministic archives for all four source
trees. Archive, tree, file-count, license, image, and public-result hashes are
recorded in [source-lock.json](source-lock.json). Once the pinned base image is
available, both images build and run without network access.

## Real differential verifier

For each of 15 hidden cases, the separate verifier:

1. validates all four source archives and all 430 pristine Seurat files;
2. permits only `R/enrichment.R` plus one NAMESPACE export;
3. executes the exact locked `clusterProfiler::enricher` source entry point and
   the locked DOSE/qvalue functions it delegates to;
4. removes the pristine host, all donor/reference sources, the reference
   runner, and the source archives;
5. runs the candidate as UID 10001 with `/testbed` read-only, `/tests`
   unreadable, forbidden donor packages absent, and no network;
6. compares exact term/hit/ratio fields and p, adjusted-p, and q values at
   `1e-12` absolute-or-relative tolerance.

Hard gates also cover R syntax, exact patch shape, forbidden imports/processes,
64/96-token donor-fragment scanning, nine malformed input classes, canonical
ordering/types, and BH/hit-set invariants. Hidden fixtures cover Seurat marker
tables, duplicate/unmapped IDs, custom universes, inclusive boundaries, extreme
tails, p/q filtering, Unicode names, reordered annotations, empty hits, missing
names, and the all-small-p q-value edge case.

## Acceptance evidence

| Scenario | Result |
|---|---:|
| Formal Harbor Oracle | `15/15`, reward `1.0` |
| Formal Harbor NOP | reward `0.0` |
| BH-used-as-qvalue near miss | `1/15`, reward `0.0666667` |
| Forbidden clusterProfiler dependency | hard gate, reward `0.0` |
| Invalid input checks | `9/9` |
| Public examples in Agent image | `5/5` |

The accepted Oracle and NOP jobs each completed one trial with zero exceptions
and zero retries. Their locked task digests are identical. Oracle numeric errors
were exactly zero for all compared probability fields on these fixtures.
Reports, locks, rewards, results, artifact manifests, and checksums are under
[validation/evidence](validation/evidence).

## Run with Harbor

With Harbor 0.20+ and Docker available:

```bash
harbor run --path . --agent oracle --job-name algobridge-0004-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0004-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

`environment_mode = "separate"` means only `/testbed` crosses from the Agent
phase into a fresh verifier container. The task needs Linux x86_64, Docker or a
compatible Harbor backend, 4 CPUs, about 8 GB RAM, and 12 GB temporary storage.
It is CPU-only and does not require an H200 or any GPU.

