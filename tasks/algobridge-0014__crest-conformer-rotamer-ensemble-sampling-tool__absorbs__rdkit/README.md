# ALGOBRIDGE-0014: CREST absorbs RDKit

Accepted Harbor single-step algorithm-migration Task. The bounded target
is RDKit 2026.03.5 ETKDG distance-geometry conformer initialization inside the
locked CREST 3.0.2 source tree.

## Acceptance state

Official host and donor commits, complete ordinary tracked-source archives, an
immutable Python base image, and offline RDKit runtime wheels are
provenance-locked. Harbor 0.20.0 accepted the clean-room Oracle at Reward `1.0`
and rejected the pristine-host NOP at Reward `0.0`. The Oracle passes public
`5/5`, hidden `15/15`, invalid-contract `12/12`, and metamorphic `2/2` checks.

Exact commits, trees, archive policy, file counts, hashes, and wheel identities
are recorded in [`source-lock.json`](source-lock.json).
Formal machine-readable evidence and interpretation are recorded in
[`validation/HARBOR_ACCEPTANCE.md`](validation/HARBOR_ACCEPTANCE.md).
