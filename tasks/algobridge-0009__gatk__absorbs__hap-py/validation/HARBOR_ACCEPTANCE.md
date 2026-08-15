# Harbor acceptance: ALGOBRIDGE-0009

## Formal runs

- Harbor: `0.20.0`
- Functional task commit: `418d59a9a0d271bc20cb3101570250aff8146584`
- Locked task digest shared by both jobs:
  `sha256:8678081afdb5d1a542f4de10fedf2036593611defb55cecdcb0aa6f2fcb60bac`
- Oracle job: `algobridge-0009-oracle-final-20260815`
- Oracle trial: `algobridge-0009__gatk__absorbs__XQ3CzuF`
- Oracle reward: `1.0`; exceptions: none
- NOP job: `algobridge-0009-nop-final-20260815`
- NOP trial: `algobridge-0009__gatk__absorbs__J4ben4Q`
- NOP reward: `0.0`; exceptions: none

Both formal jobs forced fresh Docker builds with CPU and memory enforcement
ignored only at the local Harbor adapter boundary. The verifier itself used the
task's locked no-network, separate-environment configuration.

## Oracle verification

The native GATK Java solution passed every gate:

- source integrity, import policy, and donor-copy scan: pass
- archive, patch, binary, JDK, and version provenance: pass
- candidate UID 10001 isolation from every protected reference path: pass
- disclosed scientific cases: `5/5`
- hidden scientific cases: `15/15`
- malformed-input contract: `12/12`
- truth/query swap and coordinate-shift metamorphic checks: `2/2`

The root-only oracle ran the official hap.py `v0.3.15` xcmp engine with forced
bounded haplotype comparison and then applied hap.py's quantification rule that
promotes records in a `HapMatch` block to TP. Candidate code executed only after
the packet boundary and could not read the oracle, donor, source locks, hidden
cases, or harness source.

## Negative controls

The pristine GATK host received Reward `0.0` because the exact required Java
addition was absent. A realistic near miss retaining validation and literal
position/REF/ALT/genotype matching but disabling haplotype equivalence received
Reward `0.6` (`12/20` scientific cases). It failed shifted homopolymer indels,
compound representations, and mixed blocks, demonstrating that full reward
requires the migrated hap.py-style capability rather than row-wise VCF matching.

## Evidence files

`validation/evidence/` contains the formal job locks, job and trial results,
artifact manifests, full Oracle/NOP verifier reports, and the isolated
exact-only near-miss report. Formal JSON files are copied byte-for-byte from the
corresponding Harbor job directories.
