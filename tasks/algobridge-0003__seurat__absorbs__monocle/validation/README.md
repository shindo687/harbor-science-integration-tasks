# Validation

`generate_public_examples.R` invokes the locked real Monocle3 reference and
regenerates the five published input/expected pairs.

`evidence/` contains exact machine-readable copies from the accepted Harbor
Oracle and NOP jobs: job results and locks, trial results and task locks,
artifact manifests, and verifier reports. `HARBOR_ACCEPTANCE.md` records their
identifiers and interpretation.

`apply_euclidean_chain_near_miss.py` creates the documented scientific near
miss. It retains graph projection and shortest-path pseudotime but replaces the
locked downstream cell-chain weight semantics with the more obvious Euclidean
distance; the hidden verifier reduces it to `5/15`.
