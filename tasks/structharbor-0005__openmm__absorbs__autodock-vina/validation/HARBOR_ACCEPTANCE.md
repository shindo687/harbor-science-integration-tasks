# Formal Harbor acceptance

Accepted with Harbor 0.20's local Docker provider on 2026-08-15. Both formal
trials used `environment_mode = "separate"` and
`network_mode = "no-network"`; each completed once with no retry or exception.

## Oracle

- Job: `structharbor-0005-oracle-final-20260815`
- Job result ID: `39acdd10-7f30-4bbd-8d06-a857d8ecdf6e`
- Trial: `structharbor-0005__openmm__absor__FDBox6U`
- Trial result ID: `7548de0e-ed73-4a18-aa40-19157337dfc6`
- Trial task checksum: `0ee2ac3a90b7d0633da5b2e46d54874ad3e49ec87046f8e1fb986977cdf33f2b`
- Task lock digest: `sha256:92b831730f85a15c62c7c07f53d5d643241b94ed8d6d6d71d5324b3ea033c385`
- Result: one completed trial, zero errors, Reward `1.0`
- Verifier: source/provenance/isolation gates passed; public `5/5`, hidden
  `15/15`, invalid `10/10`

## NOP

- Job: `structharbor-0005-nop-final-20260815`
- Job result ID: `91ca7358-e0ce-465a-98fd-3f5d6a704e8a`
- Trial: `structharbor-0005__openmm__absor__oH7Tzef`
- Trial result ID: `b4a30d8f-24a8-4c9d-812a-105aa22715ff`
- Trial task checksum: `77025e6a96f544e01d462bef76517b2a4899e3d0d3a2db57b54fbf004c35a7e1`
- Task lock digest: `sha256:92b831730f85a15c62c7c07f53d5d643241b94ed8d6d6d71d5324b3ea033c385`
- Result: one completed trial, zero errors, Reward `0.0`
- Verifier: source gate rejected the missing integration module as expected

## Interpretation

The clean-room Oracle matches the locked native Vina 1.2.7 potentials on all
five disclosed and fifteen hidden typed poses. Pair inclusion and identities
match exactly. The maximum observed pair-term energy error is `4.44e-16`
kcal/mol; the maximum coordinate-force error is `2.14e-10`
kcal/mol/angstrom. The candidate UID could not read any of the six protected
reference, source, test, pristine-host, or archive paths.

The NOP proves pristine OpenMM lacks the requested module. A scientific near
miss that ignores rotatable-bond normalization passes only `4/15` hidden cases
(Reward `0.2666666667`), demonstrating that the verifier checks torsional
normalization as well as the five intermolecular terms.

The functional task files exercised by both formal trials were committed at
`7a7f649bbe514db6d88d3748ca6b910bce445593`; accepted-state metadata and the
copied machine-readable evidence were added afterward.
