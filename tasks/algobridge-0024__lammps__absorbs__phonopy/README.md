# ALGOBRIDGE-0024: LAMMPS absorbs phonopy FC2 reconstruction

An accepted single-step Harbor task in which an Agent adds native harmonic
force-constant reconstruction and q-point phonons to LAMMPS. The implementation
must reproduce a real locked `LAMMPS -> phonopy` workflow, then run with neither
phonopy nor its Python numerical stack present.

## Capability to implement

The Agent may add only:

```text
src/fit_harmonic_fc2.cpp
src/fit_harmonic_fc2.h
```

These files register a serial LAMMPS command:

```text
fit_harmonic_fc2 INPUT.json OUTPUT.json
```

The command fits full supercell FC2 from finite-displacement force responses,
projects permutation symmetry and both acoustic sum-rule axes, constructs
mass-normalized complex dynamical matrices, and returns ascending eigenvalues,
signed frequencies, and complex eigenvectors. See [instruction.md](instruction.md)
for the bounded JSON contract.

## Locked inputs

| Component | Lock |
|---|---|
| LAMMPS host | `9e42b6f0f2c68a092d5847d4127a053dc50e126a` |
| phonopy donor | `4bac506220d426784020ea24812c93e2a016be18` |
| Base image | `python:3.12.11-bookworm` by digest |
| Reference backend | locked phonopy official C extension |

Archive, tree, license, image, and offline-wheel hashes are recorded in
[source-lock.json](source-lock.json). The repository includes everything needed
for image construction; dependency installation during the build is offline.

## Real differential verifier

For each of 15 hidden cases, the separate verifier:

1. checks all 9,677 locked LAMMPS files and permits only the two candidate files;
2. runs pristine LAMMPS for baseline and every finite displacement;
3. passes those real forces to pristine phonopy's traditional FC2 path;
4. deletes pristine LAMMPS, phonopy source, and phonopy runtime;
5. clean-builds modified LAMMPS and checks its dynamic dependencies;
6. runs the candidate unprivileged with a read-only `/testbed`;
7. compares FC2, diagnostics, dynamical matrices, eigenvalues, signed
   frequencies, and degenerate eigenspace projectors.

Hard gates also cover original LAMMPS behavior, 11 malformed-input classes,
record and atom reordering, coordinate rotation, force scaling, q periodicity,
Hermiticity, orthogonality, eigen residuals, and the Gamma acoustic subspace.
Candidate execution has no donor runtime and no network.

## Acceptance evidence

| Scenario | Result |
|---|---:|
| Formal Harbor Oracle | `15/15`, reward `1.0` |
| Formal Harbor NOP | reward `0.0` |
| No ASR/permutation projection near miss | reward `0.0` |
| Forbidden donor dependency | reward `0.0` |
| Public examples | `5/5` |

Both formal jobs completed one trial with zero Harbor exceptions. Reports,
locks, results, rewards, artifact manifests, and checksums are under
[validation/evidence](validation/evidence).

## Run with Harbor

With Harbor 0.20+ and Docker available:

```bash
harbor run --path . --agent oracle --job-name algobridge-0024-oracle \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes

harbor run --path . --agent nop --job-name algobridge-0024-nop \
  --n-concurrent 1 --cpus ignore --memory ignore --force-build --yes
```

`environment_mode = "separate"` makes Harbor collect `/testbed` after the
Agent phase, stop that environment, start the verifier image, restore the
artifact, and only then invoke `/tests/test.sh`.

The task needs Linux x86_64, Docker or a compatible Harbor backend, 8 CPUs,
about 16 GB RAM, and 20 GB temporary storage. It does not need a GPU or H200.
