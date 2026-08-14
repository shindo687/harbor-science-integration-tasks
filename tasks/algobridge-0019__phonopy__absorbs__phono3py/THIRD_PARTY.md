# Third-party material

The Agent environment contains the locked phonopy source snapshot under the
BSD-3-Clause license and a read-only phono3py source snapshot for documentation.

The separate verifier installs wheels built directly from both locked commits.
The real reference calls phono3py's `Phono3py.produce_fc3` with its declared
symfc backend.  symfc 1.7.3 is available only inside the reference runtime and
is physically removed, together with phono3py, before candidate execution.

The Agent environment intentionally contains neither phono3py nor symfc.  It
does contain phonors, the locked phonopy release's ordinary backend for atomic
permutation matching; the submitted module may reach it only through existing
phonopy structure/symmetry APIs.  The clean-room Oracle and intended candidate
module use NumPy/SciPy linear algebra and phonopy's existing objects, but no
third-party FC3 implementation or copied donor code.
