# Third-party material

The Agent environment contains a locked AlphaFold 2 source snapshot under the
Apache-2.0 license and a read-only ProDy source snapshot for API documentation.

The separate verifier contains a wheel built from the locked ProDy commit and
its offline dependencies.  ProDy is MIT-licensed and its `LICENSE.rst` records
the licenses of bundled Biopython, pyparsing, KDTree, and SciPy-derived
components.  All donor runtime and source files are removed before candidate
execution.

No ProDy code is part of the clean-room Oracle or intended candidate module.

