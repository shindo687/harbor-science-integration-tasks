# Validation

The verifier uses a separate offline container. It authenticates the locked
GROMACS and DSSP inputs, computes references with real `mkdssp 4.4.11`, then
deletes the executable, donor source, fixtures, archives, and reference runner
before compiling or executing the candidate. Candidate tests run as UID/GID
10001.

Accepted validation results:

- Oracle: public 5/5, hidden 15/15, malformed input 10/10, Reward 1.0.
- NOP/pristine GROMACS: source hard gate, Reward 0.
- Five public examples in the Agent image: 5/5 without network access.
- Formal Harbor 0.20.0: Oracle 1.0 and NOP 0; both jobs completed with one
  trial, zero retries, and zero exceptions.

`generate_public_examples.py` regenerates the disclosed fixtures through the
same locked real reference adapter when run inside the verifier runtime.

Formal job and trial IDs:

- Oracle job `bca4a517-e607-4913-b190-7e74cfe87634`, trial
  `6bc3e6ab-9796-403b-aec2-a5a3c5aa6055`.
- NOP job `dd25a941-f132-4138-a59e-eddfa02a560c`, trial
  `75007034-6c32-414a-acbf-2896fe51a742`.

`evidence/` contains immutable copies of the Harbor job/trial results, locks,
artifact manifests, verifier reports, rewards, and direct-run reports.
`evidence/SHA256SUMS` authenticates every evidence file.
