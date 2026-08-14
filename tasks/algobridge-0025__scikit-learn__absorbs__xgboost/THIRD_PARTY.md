# Third-party material

The Agent environment contains locked upstream source for development and
documentation:

- scikit-learn `e27ccf58592fcfe8c7ca87f53dde840c436093b2`, BSD-3-Clause;
- XGBoost `a3e3df59b83e1f230bb238c99dbaf63d8382ed24`, Apache-2.0;
- XGBoost submodule dmlc-core
  `4baa84e627849e675a3f99c92990ef9c39e4269e`, Apache-2.0.

The verifier alone contains a CPU-only XGBoost reference runtime built from
the locked donor commit. Candidate execution occurs only after the runtime,
donor source, reference runner, and reference outputs have been removed.

The requested implementation is clean-room and must not vendor or copy donor
implementation code. Exact commit, tree, archive, reference-library, base-image,
and wheel-manifest hashes are recorded in `source-lock.json`. The complete
upstream license files remain present in both locked source snapshots.
