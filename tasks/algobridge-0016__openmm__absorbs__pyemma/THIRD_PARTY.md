# Third-party material

The task environment contains a locked OpenMM source snapshot.  OpenMM is
distributed under MIT and LGPL-2.1-or-later terms; see the license files inside
that snapshot.

The separate verifier contains PyEMMA commit
`3327f28b49e388e1ce4a6a83ab2f0c0ac7ca5050` (`v2.5.12-6-g3327f28b`) and its
offline reference dependencies, including `deeptime==0.4.5`.  PyEMMA is
LGPL-3.0-or-later.  These files are verifier fixtures only and are removed
before candidate execution.

No PyEMMA or deeptime source is part of the Oracle solution or intended
candidate implementation.
