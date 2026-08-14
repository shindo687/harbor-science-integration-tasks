# Validation

`generate_public_examples.py` executes the locked real TB2J reference and
regenerates the five published input/expected pairs.

`evidence/` contains exact machine-readable copies from the accepted Harbor
Oracle and NOP jobs: job results and locks, trial results and task locks,
artifact manifests, and verifier reports. `HARBOR_ACCEPTANCE.md` records their
identifiers and interpretation.

`apply_always_ferromagnetic_sign_near_miss.py` creates the documented
scientific near miss used to check hidden-test discrimination. It retains the
Green-function calculation but incorrectly assumes every magnetic pair is
ferromagnetically aligned.
