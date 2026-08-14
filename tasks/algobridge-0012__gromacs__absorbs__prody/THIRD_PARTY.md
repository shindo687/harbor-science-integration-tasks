# Third-party material

The Agent image contains the exact locked GROMACS source snapshot under
LGPL-2.1-or-later and a read-only ProDy source snapshot for documentation under
the MIT license (including ProDy's documented bundled third-party notices).

The separate verifier installs the exact ProDy wheel only in a private
reference runtime. It computes every reference result first, then physically
removes that runtime, the donor source, reference runner, wheels, and pristine
host before executing candidate code as an unprivileged user. The Agent image
contains no installed ProDy, SciPy, or Biopython package. Candidate numerical
code uses GROMACS's existing NumPy dependency only.
