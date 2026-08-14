# ALGOBRIDGE-0021: Wannier90 absorbs TB2J

This Harbor single-step task asks an agent to add native collinear
Liechtenstein exchange evaluation to a locked Wannier90 source tree. The
verifier compares the new Fortran routine with an independently locked, real
TB2J `0.9.19` `ExchangeCL2`/`TBGreen`/`Contour` execution.

The bounded interface accepts explicit spin-resolved two-site, two-orbital
one-dimensional Wannier Hamiltonians. The matrix covers ferromagnetic and
antiferromagnetic states, complex/asymmetric hopping, several odd k meshes and
contours, Fermi-level shifts, orbital-gauge rotations, malformed input, and a
spin-degenerate rejection case. It does not claim arbitrary orbital counts,
higher-dimensional meshes, spin-orbit exchange tensors, or structural I/O.

Harbor runs the agent and verifier sequentially in separate no-network
containers. The agent sees Wannier90 plus read-only TB2J source. The verifier
restores only the modified `/testbed`; its executable TB2J reference, hidden
generator, and offline wheel environment are root-only. Candidate code is
compiled and run as UID 10001 and cannot read the reference tree. See
[instruction.md](instruction.md), [source-lock.json](source-lock.json), and
[THIRD_PARTY.md](THIRD_PARTY.md).

Status: **accepted**. Formal Harbor 0.20 trials completed with Oracle hidden
tests `15/15` (Reward `1.0`), NOP Reward `0.0`, and zero trial exceptions. The
full Oracle matrix also passed public `5/5`, invalid `10/10`, and metamorphic
`2/2`. A deliberately always-ferromagnetic-sign scientific near miss scored
only `11/15` hidden cases, demonstrating useful discrimination.

See [validation/HARBOR_ACCEPTANCE.md](validation/HARBOR_ACCEPTANCE.md) for exact
job/trial identifiers and [validation/README.md](validation/README.md) for the
evidence model.
