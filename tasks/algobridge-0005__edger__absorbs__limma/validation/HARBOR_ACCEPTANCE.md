# Harbor acceptance

Accepted on 2026-08-15 with Harbor 0.20.0.

## Oracle

- job: `algobridge-0005-edger-limma-oracle-r5-20260815`;
- job result ID: `c79a91e5-5a10-4c17-b140-c978ad9e345e`;
- trial result ID: `88f0f353-3fb4-4325-aef3-e9fb40847cef`;
- task checksum: `f4994aeb6122d02dffb56cf25df8c1af5db325be393e66f91bac2772a722cfa2`;
- trials: 1 completed, 0 errored;
- Reward: `1.0`;
- hidden real differential cases: `15/15`;
- public examples: `5/5`;
- malformed inputs rejected: `10/10`;
- reference integrity and two deterministic runtime replays: pass;
- source policy and 64/96-token donor-fragment scan: pass;
- candidate UID/read-only artifact/verifier-file isolation: pass;
- unchanged edgeR host-source parity: pass.

## NOP negative control

- job: `algobridge-0005-edger-limma-nop-20260815`;
- job result ID: `e1ca0117-9797-4885-baff-f194ee09c4b8`;
- trials: 1 completed, 0 errored;
- Reward: `0.0`;
- failure point: required `R/voomFit.R` source-policy hard gate.

The reference phase runs unchanged locked edgeR `calcNormFactors.default`,
limma `voom`, `lmFit`, `contrasts.fit` and `eBayes` twice before candidate
execution. The verifier then deletes the pristine host, limma/statmod sources,
reference runner and source archives. The submitted edgeR tree is frozen
read-only and executed as UID 10001 while `/tests` is unreadable and networking
is disabled.
