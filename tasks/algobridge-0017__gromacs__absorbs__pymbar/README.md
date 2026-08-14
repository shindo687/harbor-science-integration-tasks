# ALGOBRIDGE-0017: GROMACS absorbs pymbar BAR

An accepted single-step Harbor task in which an Agent adds a native, bounded
Bennett acceptance-ratio estimator to GROMACS. The implementation reproduces a
real locked `GROMACS -> pymbar` workflow, then runs with pymbar and its Python
numerical stack physically absent.

## Capability to implement

The Agent may make exactly two source changes:

```text
add    src/gromacs/gmxana/gmx_bar_internal.cpp
modify src/programs/legacymodules.cpp (command wiring only)
```

These changes register a native GROMACS command:

```text
gmx bar-internal -f INPUT.bar -o OUTPUT.json
```

It accepts forward and reverse dimensionless reduced-work samples, solves the
unequal-population BAR equation with stable log-domain arithmetic, and reports
`delta_f`, asymptotic BAR uncertainty, two-state overlap, iteration/evaluation
counts, and the equation residual. See [instruction.md](instruction.md) for the
exact protocol and bounds.

## Locked inputs

| Component | Lock |
|---|---|
| GROMACS host | tag `v2024.6`, commit `a7455395479a6eeebb8f5676ea580898c7662d21` |
| pymbar donor | commit `ed40ec3bbef03bb08938ad1a74d459b0d1ab81f7` |
| Base image | `python:3.12.11-bookworm` by digest |
| Build tools | offline CMake 3.31.6 and Ninja 1.11.1.3 wheels |
| Reference runtime | offline NumPy 2.3.2, SciPy 1.16.1, numexpr 2.14.1 wheels |

Archive, tree, license, image, and wheel hashes are recorded in
[source-lock.json](source-lock.json). Both images install task dependencies
offline; the repository contains the required source archives and wheels.

## Real differential verifier

For each of 15 hidden cases, the separate verifier:

1. validates the locked archives and all 8,124 pristine GROMACS files;
2. permits only the native module and constrained command registration change;
3. runs each work series through pristine `gmx analyze`, then evaluates it with
   locked `pymbar.bar` and `pymbar.bar_overlap`;
4. deletes pristine GROMACS, pymbar source, the reference runner, NumPy, SciPy,
   and numexpr before candidate configuration or compilation;
5. clean-builds modified GROMACS and checks its dynamic dependencies;
6. runs the candidate as UID 10001 with read-only `/testbed` and no network;
7. compares `delta_f`, uncertainty, overlap, diagnostics, and a separately
   recomputed BAR equation residual.

Hard gates also cover 12 malformed input/CLI classes, original GROMACS
behavior, donor-fragment scanning, swap/sign antisymmetry, energy-zero
covariance, and replication uncertainty scaling. Hidden fixtures include
unequal populations, low overlap, one sample per direction, warm starts, and
work magnitudes up to 900.

## Acceptance evidence

| Scenario | Result |
|---|---:|
| Formal Harbor Oracle | `15/15`, reward `1.0` |
| Formal Harbor NOP | reward `0.0` |
| Equal-population-assumption near miss | reward `0.0` |
| Forbidden pymbar dependency control | reward `0.0` |
| Invalid input/CLI checks | `12/12` |
| Public examples in Agent image | `5/5` |

The direct Oracle's largest absolute errors were `3.64e-12` for `delta_f`,
`1.32e-13` for uncertainty, and `1.86e-13` for overlap. Both formal Harbor jobs
completed one trial with zero platform exceptions. Reports, locks, results,
rewards, artifact manifests, and checksums are under
[validation/evidence](validation/evidence).

## Run with Harbor

With Harbor 0.20+ and Docker available:

```bash
harbor run --path . --agent oracle --job-name algobridge-0017-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0017-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

`environment_mode = "separate"` makes Harbor collect `/testbed` after the
Agent phase, stop that environment, start the verifier image, restore the
artifact, and only then invoke `/tests/test.sh`.

The task needs Linux x86_64, Docker or a compatible Harbor backend, 8 CPUs,
about 16 GB RAM, and 20 GB temporary storage. It does not need a GPU or H200.
The first verifier image build compiles pristine GROMACS; each verifier trial
then clean-builds the candidate, so a formal Oracle run takes several minutes.
