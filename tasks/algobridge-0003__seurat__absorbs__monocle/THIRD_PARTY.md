# Third-party material

- **Seurat** — official repository commit
  `258a250c7b27e70f6651443d9835cd3c289c51ee`, MIT. The task archives the
  complete tracked source tree at that commit.
- **Monocle3** — official `v1.4.26` commit
  `4f4239a0afb0dd1941a0359ba6bec95eb0ccf628`, MIT. Its complete tracked
  source is supplied read-only for study and separately to the verifier. The
  requested answer must be a clean-room implementation and must not call or
  depend on this package.
- **Verifier runtime** — Biocontainers image
  `quay.io/biocontainers/r-monocle3@sha256:513fa87e98bebc2bc81442d779788866acfe9c29d42ec345db65d9818405050a`
  provides the real Monocle3 `1.4.26` package and its R dependencies. Candidate
  execution is unprivileged and cannot read the Monocle3 package or reference
  source.

The archive boundaries, Git trees, and exact hashes are recorded in
`source-lock.json`.
