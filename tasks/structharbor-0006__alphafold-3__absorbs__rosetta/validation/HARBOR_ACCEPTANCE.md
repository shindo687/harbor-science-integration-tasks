# Harbor acceptance record

Accepted with Harbor `0.20.0` on 2026-08-16.

| Control | Job | Trial | Reward | Expected |
|---|---|---|---:|---:|
| Oracle | `structharbor-0006-oracle-final-20260816` | `structharbor-0006__alphafold-3__JLRfvi6` | 1.0000000000 | 1 |
| NOP | `structharbor-0006-nop-20260816` | `structharbor-0006__alphafold-3__UcUv5Q9` | 0.0000000000 | 0 |
| No-H-bond near miss | `structharbor-0006-near-hbond-20260816` | `task__mHwmbbj` | 0.7668478261 | `< 1` |

The oracle passed all 23 differential cases, all 10 force cases, all 12 invalid
input rejections, all three invariants, the independent `1e-4` force check, and
the eight-case Rosetta ranking calibration (`Spearman = 1.0`, threshold 0.98).
The verifier confirmed that the candidate UID could not read `/tests`, the
pristine host, or source archives, and that the locked AlphaFold 3 tree was
unchanged except for the one allowed module.

The final oracle ran against functional task commit
`44724d3b0fd587d74de74154db7d55c9bcc20ee4`; subsequent commits add only this
acceptance record and the captured Harbor evidence under `validation/evidence/`.

The near miss deliberately returned zero for the orientation-aware H-bond term.
It failed the single-H-bond fixture, mixed public fixture, and seven matching
hidden fixtures while retaining the unrelated Rosetta compression ranking.

The calibration contains eight rigid variants of the same 8ZR4 fragment
(`H:109-115`, `A:263-269`) evaluated with locally licensed Rosetta 2025.03
InterfaceAnalyzer/ref2015 and deterministic settings.  Only coordinates and
scalar results are distributed.  The JSON and local binary hashes are locked in
`source-lock.json`; the formal images contain no Rosetta source, runtime,
database, or parameters.
