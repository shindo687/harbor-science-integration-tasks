# Author validation

The task is accepted only after all of these controls succeed:

1. clean-room Oracle: 15/15 hidden cases and reward 1.0;
2. pristine Seurat NOP: reward 0.0;
3. BH-as-qvalue scientific near miss: does not receive full credit;
4. dormant clusterProfiler call: rejected by a hard dependency gate;
5. five public examples: 5/5;
6. formal Harbor Oracle and NOP: one trial each, zero platform exceptions.

The verifier independently checks the four source archives, all 430 pristine
Seurat files, the exact allowed patch shape, R syntax, forbidden imports and
execution primitives, 64/96-token donor fragments, nine malformed inputs, and
the candidate's unprivileged filesystem isolation. It computes all reference
answers with the locked original sources before deleting the reference tree.

Machine-readable reports, rewards, formal job metadata, artifact manifests,
and their checksums are stored in `validation/evidence/` only after each run
has actually completed.

Accepted results on 2026-08-14:

| Control | Result |
|---|---:|
| Direct Oracle | 15/15, 1.0 |
| Direct NOP | 0.0 |
| Direct BH-as-qvalue near miss | 1/15, 0.0666667 |
| Direct forbidden dependency | hard gate, 0.0 |
| Public examples | 5/5 |
| Formal Harbor Oracle | 1 trial, 0 exceptions, 1.0 |
| Formal Harbor NOP | 1 trial, 0 exceptions, 0.0 |

Both final formal jobs lock the same packaged task digest:
`sha256:d353b1f4f3457b659d724e434256b2379b53ceadfd16be54a27990b70cb1f4db`.
