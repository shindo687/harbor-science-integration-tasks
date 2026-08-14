# Third-party materials

## LAMMPS

- Upstream: <https://github.com/lammps/lammps>
- Commit: `9e42b6f0f2c68a092d5847d4127a053dc50e126a`
- License: GPL-2.0-only; the upstream `LICENSE` is present in the host archive.
- Role: editable host source and pristine verifier source.

The archived host snapshot excludes only data-heavy benchmark inputs, examples,
and potential parameter files. It retains the complete core source, build files,
documentation, tests, tools, and language interfaces needed for this task.

## phonopy

- Upstream: <https://github.com/phonopy/phonopy>
- Commit: `4bac506220d426784020ea24812c93e2a016be18`
- License: BSD-3-Clause; the upstream `LICENSE` is present in the donor archive.
- Role: private reference implementation and readable donor source in the Agent
  environment. It is physically absent from the candidate runtime.

The solution must be a clean-room implementation and must not copy donor code.

