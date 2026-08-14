# ALGOBRIDGE-0020: Quantum ESPRESSO absorbs BoltzTraP2

Authoring repository for a Harbor single-step algorithm-migration task. The
task asks an agent to add bounded, constant-relaxation-time electronic
transport moments to the locked Quantum ESPRESSO 7.5 source tree, while the
separate verifier compares it against unchanged BoltzTraP2 25.3.1.

Status: **accepted**. Formal Harbor 0.20 trials completed with Oracle `15/15`
(`1.0`), NOP `0.0`, and zero trial exceptions. Direct evidence also includes a
temperature-capped scientific near miss at `13/15`, demonstrating useful
hidden-test discrimination.

See `validation/HARBOR_ACCEPTANCE.md` for exact job/trial identifiers and
`validation/README.md` for the evidence model.
