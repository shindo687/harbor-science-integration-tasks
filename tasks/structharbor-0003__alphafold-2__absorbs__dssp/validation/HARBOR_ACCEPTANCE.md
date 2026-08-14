# Formal Harbor acceptance

Accepted with Harbor 0.20's local Docker provider on 2026-08-15. Both formal
trials used `environment_mode = "separate"` and
`network_mode = "no-network"`; each completed once with no retry or exception.

## Oracle

- Job: `structharbor-0003-oracle-final-20260815`
- Job result ID: `f271dc82-7b18-4d34-bc6e-bc4348bd9cb4`
- Trial: `structharbor-0003__alphafold-2__awXfBeQ`
- Trial result ID: `61ee37fd-60ee-4402-8e68-78b5bd0ff221`
- Trial task checksum: `e6d804d718897b37a351d435d93bd7cb6ea140857155532fbbfc9ca199364461`
- Task lock digest: `sha256:9b578a69105532abfa99c740b304813fa9e8fa42ed0c9b9c5517a9b2e61ea405`
- Result: one completed trial, zero errors, Reward `1.0`
- Verifier: source/provenance/isolation gates passed; public `5/5`, hidden
  `15/15`, invalid `10/10`

## NOP

- Job: `structharbor-0003-nop-final-20260815`
- Job result ID: `b8e48d1a-202d-4e8e-a2e5-6af57b64bd74`
- Trial: `structharbor-0003__alphafold-2__HThxdBo`
- Trial result ID: `e746bb47-7d09-4886-9720-99cf62ffa1c4`
- Trial task checksum: `51139668d53a9915807b7583498cc46a3657176e53b0493c5bbddb2d4f3ce060`
- Task lock digest: `sha256:9b578a69105532abfa99c740b304813fa9e8fa42ed0c9b9c5517a9b2e61ea405`
- Result: one completed trial, zero errors, Reward `0.0`
- Verifier: source gate rejected the missing integration module as expected

## Interpretation

The Oracle proves that the clean-room AlphaFold-side implementation reproduces
real `mkdssp 4.4.11` across mixed alpha/beta structures, rigid transforms,
small perturbations, crops, and single/multi-chain cases. Secondary-structure
codes and all top-two H-bond partner indices match exactly. The largest energy
difference is `0.05`, within the unavoidable half-unit of the reference's
one-decimal legacy rendering.

The NOP proves that pristine AlphaFold2 does not already expose the requested
API. A scientific near miss that disables beta-bridge/ladder detection passes
only `4/15` hidden cases (Reward `0.266666666667`), demonstrating that the
verifier checks the donor algorithm rather than only the interface.

The functional task files exercised by the final Harbor trials were committed
at `5b277ed140d7c80d1a8346b8af06700d1edf345e`; accepted-state metadata and the
copied machine-readable evidence were added afterward.
