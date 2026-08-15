## Task

Work in the HH-suite source tree at `/testbed`. Add a native, bounded CPU
pseudo-likelihood Potts contact scorer named `hhcontacts`.

The Agent image contains read-only CCMpred source at `/opt/donor-source` for
study. Your submitted HH-suite tree must be a standalone implementation: it
must not execute, import, dynamically link, download, vendor, or otherwise
require CCMpred or `libconjugrad` at build time or runtime.

## Required interface

Register and install an HH-suite CMake executable target named `hhcontacts`.
The following command must work:

```bash
./hhcontacts \
  --input ALIGNMENT.a3m \
  --output CONTACTS.json \
  --reweight-threshold 0.8 \
  --l2 0.2 \
  --iterations 50 \
  --seed 0
```

The bounded input contract is:

- A3M with 2 through 500 records and 2 through 80 match-state columns;
- the 20 standard amino acids plus `-` in match states;
- lowercase A3M insertions and `.` insertion gaps are removed;
- unique ASCII identifiers made from letters, digits, `_`, `.`, and `-`;
- reweight threshold in `(0,1]`, positive finite L2 factor, 1 through 250
  iterations, and a non-negative integer seed.

The optimizer is deterministic; `seed` is retained in the interface and output
for pipeline reproducibility but must not change the deterministic result.

Write one JSON object with exactly these top-level fields:

- `schema_version` (integer `1`), `length`, `sequence_count`, and
  `effective_sequences`;
- `parameters` containing `reweight_threshold`, `l2_factor`, `iterations`, and
  `seed`;
- `diagnostics` containing at least finite `objective`,
  `iterations_completed`, `evaluations`, and `status`;
- `raw_score` and `apc_score`, each an `L x L` numeric matrix;
- `top_contacts`, the highest-scoring sequence-separation-at-least-5 pairs,
  using 1-based `i`, `j`, and `score`, sorted by descending score then indices.

## Algorithmic requirements

Implement the core algorithm in native HH-suite C++:

1. Parse A3M match states and encode 20 amino acids plus gap.
2. Compute CCMpred-compatible sequence weights at the requested identity
   threshold.
3. Fit all asymmetric site-conditional pseudo-likelihood terms on CPU with
   CCMpred-compatible shared symmetric couplings. Use the customary fixed
   single-site regularizer `0.01`; `--l2` is the pairwise factor applied as
   `factor * (L - 1)`.
4. Reduce the fitted 21x21 coupling blocks with CCMpred's centered Frobenius
   convention over the 20 residue states; comparison is gauge-insensitive.
5. Apply average-product correction (APC), retain the raw matrix, and emit
   deterministic ranked contacts and optimizer diagnostics.

Do not implement this as a Python, Perl, or shell wrapper. Production code must
be `src/hhcontacts.cpp`; the only other host source change permitted is the
bounded target/install registration in `src/CMakeLists.txt`. Existing HH-suite
files and behavior must remain unchanged.

The image intentionally has no CMake package, but it has the locked GNU C++
compiler. For a quick build after registering the CMake target, use:

```bash
g++ -std=c++11 -O3 -Wall -Wextra -pedantic \
  src/hhcontacts.cpp -o hhcontacts
```

## Differential grading

The separate no-network verifier computes private references with the locked
official CCMpred CPU binary, then compiles and runs only the submitted
`hhcontacts` as UID 10001. Twenty cases cover independent and coupled sites,
duplicates, gap-heavy columns, A3M insertions, short and longer alignments, and
reweighting boundaries.

For each case it checks:

- raw and APC score correlation at least `0.999`;
- top-`L/2` contact overlap at least `0.95`;
- final fixed-iteration objective absolute error at most `1e-5`;
- symmetric score matrices with zero diagonal, exact APC self-consistency, and
  deterministic contact ordering.

Provenance, clean host/source integrity, CMake registration, forbidden-runtime
policy, donor-copy detection, protected-path isolation, malformed-input
rejection, and alignment-row permutation invariance are hard gates.

Five disclosed examples are available in `/examples`. After implementing the
command, run:

```bash
/opt/task-tools/run-public-examples
```

Do not hard-code those examples: hidden lengths, rows, parameters, and residue
patterns differ.
