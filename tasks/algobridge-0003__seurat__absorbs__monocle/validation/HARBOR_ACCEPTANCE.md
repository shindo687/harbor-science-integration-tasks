# Formal Harbor acceptance

Accepted with Harbor 0.20's local Docker provider on 2026-08-15. Both trials
used `environment_mode = "separate"` and `network_mode = "no-network"`; each
completed once with no retry and no exception.

## Oracle

- Job: `algobridge-0003-seurat-monocle-oracle-r1-20260815`
- Job result ID: `f382cfb0-707d-47da-b622-7751b723ef67`
- Trial: `algobridge-0003__seurat__absorbs__o8piXx6`
- Trial result ID: `fd26d1fb-4009-4135-be59-afc8dc6af7fd`
- Task checksum: `bd387766bd7b537a2ea375b0754c13c15508d8aca0d04806623ab7d06b47719c`
- Task lock digest: `sha256:f2425b07cc957f33d02a40e485c9e8b5a4bacfdff8e4d9fee1456059c63281d5`
- Result: one completed trial, zero errors, Reward `1.0`
- Verifier: source audit passed; public `5/5`, hidden `15/15`, invalid `10/10`,
  metamorphic `2/2`

## NOP

- Job: `algobridge-0003-seurat-monocle-nop-r1-20260815`
- Job result ID: `6616091c-d6c9-46ee-a8fa-3fadb5ec890b`
- Trial: `algobridge-0003__seurat__absorbs__ZWnYbvx`
- Trial result ID: `f0b2dd1a-00be-4f87-8633-137887ca3018`
- Task checksum: `bd387766bd7b537a2ea375b0754c13c15508d8aca0d04806623ab7d06b47719c`
- Task lock digest: `sha256:f2425b07cc957f33d02a40e485c9e8b5a4bacfdff8e4d9fee1456059c63281d5`
- Result: one completed trial, zero errors, Reward `0.0`
- Verifier: source audit failed as expected; public `0/5`, hidden `0/15`,
  invalid `10/10`, metamorphic `0/2`

## Interpretation

The Oracle result proves that the native Seurat-side implementation reproduces
the locked real Monocle3 1.4.26 `project2MST` plus `order_cells` path under
candidate-process isolation. The NOP result proves that pristine Seurat does
not already expose the requested API. The Euclidean cell-chain near miss keeps
the overall graph algorithm but changes one plausible numerical choice; it
scores `5/15` hidden cases and Reward `0.333333333333`, demonstrating scientific
discrimination rather than simple interface recognition.

The functional task files exercised by the Harbor trials were committed at
`0f374c541451e0d82f232f5288c667aaa7c2a805`; this acceptance document, copied
Harbor evidence, and accepted-state metadata were added afterward.
