# Validation matrix

The release gate includes a clean-room Oracle, an unchanged-host baseline, and
a plausible scientific near miss. The near miss computes cosine similarity
against raw cell-state displacement instead of the specified centered
displacement. It preserves the API, sparse outputs, normalization, and scaling
behavior while implementing the wrong scientific quantity.

Direct verifier results from 2026-08-14 are:

- clean-room Oracle: `15/15`, Reward `1.0`, all six hard gates pass;
- unchanged Scanpy (NOP): Reward `0.0`;
- uncentered-cosine near miss: `0/15`, Reward `0.0`, while all hard gates pass;
- frozen public examples: `5/5`.

Formal Harbor 0.20 results:

- Oracle job `algobridge-0002-oracle-final`: one completed trial, zero
  exceptions, zero retries, `15/15`, Reward `1.0`, about 55 seconds;
- NOP job `algobridge-0002-nop-final`: one completed trial, zero exceptions,
  zero retries, Reward `0.0`, about 48 seconds;
- both trials use the same final task content digest and both `/testbed`
  artifacts have `status=ok`.

Evidence is stored under `evidence/`. Harbor does not expose `solution/`,
`validation/`, or verifier-private files to the Agent.
