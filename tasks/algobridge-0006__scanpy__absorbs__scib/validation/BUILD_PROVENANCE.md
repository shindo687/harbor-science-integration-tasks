# Build provenance

The source snapshots were produced from the commits recorded in
`source-lock.json`:

- Scanpy `fabadb9412c0d1cd9df9d9c2e95ac266d564ee18`;
- scIB `cd67913396b4c0430710b3d90f1d1841f5fa4468`.

The locked Scanpy wheel is
`scanpy-1.14.0.dev21+gfabadb941-py3-none-any.whl`, SHA-256
`ec8840ca54acbbee66ecce6c4f2eb979f636c27d792c3f287404153878be7131`.
The locked scIB wheel is `scib-1.1.7-py3-none-any.whl`, SHA-256
`d4f779078299ff0e9c61155f4a0c3960d2bd6fc06e5c06b5cef8446c0a2bdb25`.
Both 67-wheel manifests are identical and have SHA-256
`1994c2500dc98c0e642e521e5ca8140d8a79d57d77fdd7eafe5b299466da83f9`.

The scIB wheel contains the `knn_graph.cpp` executable built for Linux x86_64.
Its SHA-256 is
`d98f38a3028848782ecc481c7bde618233e04a40ddcf24a56761d351645a9414`;
the verifier records the same runtime hash in each accepted reference report.

Final local image IDs used for the direct acceptance run:

- Agent: `7963888a6969341a81ac189a15749124af08aeb137ffa126a49bd6a91776154a`;
- verifier: `5d5b0802884248a0d2b1b09dadd7d42584868d2ec7728cd220c019b9967d7883`.

Both Dockerfiles install only repository-carried wheels with `--no-index` and
were successfully built with container build networking disabled.
