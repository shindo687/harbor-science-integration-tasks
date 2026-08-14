# Validation

`generate_public_examples.py` executes the locked donor implementation and
regenerates the five published input/expected pairs.

`evidence/` contains exact machine-readable copies from the accepted Harbor
Oracle and NOP jobs: job results and locks, trial results and task locks,
artifact manifests, and verifier reports. `HARBOR_ACCEPTANCE.md` records their
identifiers and interpretation. `apply_always_trivial_near_miss.py` creates the
documented scientific near miss used to check hidden-test discrimination.
