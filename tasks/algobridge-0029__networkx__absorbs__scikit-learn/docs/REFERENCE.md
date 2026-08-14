# Reference pipeline and numerical contract

The reference side is fixed to the source locks in
`environment/source-lock.json`.  Its CPython 3.12 wheel is built directly from
the locked scikit-learn checkout, not downloaded from a package index.

For each case the verifier:

1. constructs a NetworkX graph and a canonical node order;
2. obtains its weighted adjacency matrix through NetworkX;
3. calls the locked `sklearn.cluster.SpectralClustering` with
   `affinity="precomputed"`, `assign_labels="kmeans"`, the case seed, ten
   initializations, and the case eigen tolerance;
4. records the label-permutation-invariant partition;
5. computes the reference normalized-Laplacian eigenspace and normalized cut;
6. terminates the reference subprocess and removes all scikit-learn files;
7. invokes only the modified NetworkX tree in an unprivileged subprocess.

The independent eigenspace/ncut calculations are mathematical observables not
exposed by `SpectralClustering`; the partition itself always comes from the
locked donor.  The verifier records provenance and checks the exact donor
wheel SHA256 before installation.

