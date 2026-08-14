# Third-party material

The task contains deterministic `git archive` snapshots. Their exact commits,
tree IDs, file counts, archive hashes, versions, and upstream URLs are recorded
in `source-lock.json`.

| Material | Purpose | License |
|---|---|---|
| Seurat 5.3.1 | Host source modified by the Agent | MIT |
| clusterProfiler 4.16.0 | Donor API and reference entry point | Artistic-2.0 |
| DOSE 4.2.0 | Locked implementation used by clusterProfiler reference | Artistic-2.0 |
| qvalue 2.40.0 | Locked q-value implementation used by DOSE | LGPL |
| R 4.5.1 base image | Agent and verifier runtime | GPL and bundled component licenses |

The requested candidate is a clean-room implementation in Seurat. The final
candidate may not import, call, bundle, or dynamically load clusterProfiler,
DOSE, qvalue, or another enrichment implementation. The separate verifier
removes all reference sources before the candidate is executed.

