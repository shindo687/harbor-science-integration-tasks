# Formal Harbor acceptance

Accepted with Harbor 0.20's local Docker provider on 2026-08-15. Both trials
used the task's `environment_mode = "separate"` and `network_mode =
"no-network"`; each completed once with no retry and no exception.

## Oracle

- Job: `algobridge-0020-qe-boltztrap2-oracle-r1-20260815`
- Job result ID: `a9ecba55-2462-4d3d-815d-4ac23669b0a3`
- Trial: `algobridge-0020__quantum-espress__G6RP9w8`
- Trial result ID: `c03272c3-7250-4866-96cc-6b59a5b3d541`
- Task checksum: `14acae8fca55cba3b4435b96a3d2b7eb928156c70eb534af31f66286a0e1f2e3`
- Task lock digest: `sha256:58b29bd06a44899cd26cee86c90b6a37b612d0f33c80fb954ee8ccdc140f9215`
- Result: one completed trial, zero errors, Reward `1.0`
- Verifier: public `5/5`, hidden `15/15`, invalid `10/10`, metamorphic `2/2`

## NOP

- Job: `algobridge-0020-qe-boltztrap2-nop-r1-20260815`
- Job result ID: `f972fb08-9a39-4c62-a4c9-d61b44a67f6a`
- Trial: `algobridge-0020__quantum-espress__bdRoTwm`
- Trial result ID: `fd0febe0-34d2-445c-8d44-f8cafedd98f9`
- Task checksum: `14acae8fca55cba3b4435b96a3d2b7eb928156c70eb534af31f66286a0e1f2e3`
- Task lock digest: `sha256:58b29bd06a44899cd26cee86c90b6a37b612d0f33c80fb954ee8ccdc140f9215`
- Result: one completed trial, zero errors, Reward `0.0`
- Failure reason: pristine QE did not add `PP/src/transport_moments.f90`

## Interpretation

The Oracle result proves that the clean-room QE-side implementation reproduces
the real locked BoltzTraP2 reference across the complete matrix under candidate
isolation. The NOP result proves that the unchanged upstream host cannot pass.
The additional `1000 K` temperature-cap near miss scores `13/15`, so the
verifier also detects a plausible but scientifically incomplete solution.

The functional task files exercised by these trials were committed at
`f677bded77c4562e96c3a2ef9f6be89e14285189`; this acceptance document and the
copied Harbor result artifacts were added afterward.

