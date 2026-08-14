# ALGOBRIDGE-0022: Wannier90 absorbs Z2Pack

This Harbor single-step task asks an agent to add a native Fortran Wilson-loop
routine to a locked Wannier90 source tree. The verifier compares its WCC,
largest-gap path, direct gap, and Z2 invariant against an independently locked,
real Z2Pack `v2.2.0` execution.

The bounded interface accepts explicit 4x4 Hermitian Hamiltonian meshes with two
occupied bands. The matrix covers ordinary and random-basis BHZ-family cases,
small gaps, energy rescaling, malformed input, and exact gap closure. It does not
claim adaptive refinement, arbitrary band counts, or 3D invariants.

Harbor runs the agent and verifier sequentially in separate no-network
containers. The agent sees Wannier90 plus read-only donor source. The verifier
restores only the modified `/testbed`; its Z2Pack reference, hidden generator,
and wheel environment are root-only. Candidate code is compiled and run as UID
10001 and cannot read the reference tree. See [instruction.md](instruction.md),
[source-lock.json](source-lock.json), and [THIRD_PARTY.md](THIRD_PARTY.md).

Status: **accepted**. Formal Harbor 0.20 trials completed with Oracle hidden
tests `15/15` (Reward `1.0`), NOP Reward `0.0`, and zero trial exceptions. The
full Oracle matrix also passed public `5/5`, invalid/closure `10/10`, and
metamorphic `2/2`. A deliberately always-trivial scientific near miss scored
only `7/15` hidden cases, demonstrating useful discrimination.

See [validation/HARBOR_ACCEPTANCE.md](validation/HARBOR_ACCEPTANCE.md) for exact
job/trial identifiers and [validation/README.md](validation/README.md) for the
evidence model.
