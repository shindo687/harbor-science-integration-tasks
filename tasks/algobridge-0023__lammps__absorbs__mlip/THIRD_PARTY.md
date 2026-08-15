# Third-party materials

## LAMMPS

- Upstream: <https://github.com/lammps/lammps>
- Tag: `stable_22Jul2025_update5`
- Commit: `9e42b6f0f2c68a092d5847d4127a053dc50e126a`
- License: GPL-2.0-only; the upstream `LICENSE` is retained in the host archive.
- Role: editable host source and pristine verifier source.

The host snapshot is the already accepted ALGOBRIDGE-0024 LAMMPS snapshot. It
omits only data-heavy benchmark inputs, examples, and potential parameter
directories; all core sources and build files needed here are retained.

## MLIP-3

- Upstream: <https://gitlab.com/ashapeev/mlip-3>
- Commit: `7fe598da1de1e81d1ca222f4ab6b5d594278605c`
- License: BSD-2-Clause; the complete upstream `LICENSE` is in the donor archive.
- Role: algorithm documentation, the MTP-9 parameter fixture, and a root-only
  reference executable.

BSD 2-Clause License

Copyright (c) 2023, Alexander Shapeev (Skoltech)

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice,
   this list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

The candidate must implement the bounded inference capability without an MLIP
runtime dependency. The verifier rejects copied 64-token source windows and
physically prevents the candidate UID from reading the oracle or donor tree.

MLIP-2 was reviewed but is not included: its non-commercial/no-redistribution
terms are unsuitable for this public task artifact.
