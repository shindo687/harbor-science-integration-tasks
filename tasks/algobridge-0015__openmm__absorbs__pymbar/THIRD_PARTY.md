# Third-party source and runtime material

## OpenMM

- Repository: https://github.com/openmm/openmm
- Commit: `c6173db6e8edd705eb59172bd21e9ce69c572405`
- Tree: `71424061bd461f029827cf2d1b54c966ac6dfbe1`
- Source archive SHA-256:
  `dfbb5c7b115dc5f5c96358561773a5ed6595f3fc5ff9aed16e06a7682a1b111d`
- Licenses: MIT for the Python layer and LGPL-2.1-or-later for the core,
  with upstream third-party notices retained in the snapshot.
- Role: complete locked host tree restored as `/testbed` for the Agent and as
  private pristine/reference material in the verifier.

The verifier uses the official `openmm==8.5.2` CPython wheel, locked by SHA-256,
only to evaluate small CPU reduced-potential fixtures. The submitted estimator
is loaded from the locked 8.6-development host tree and uses no OpenMM binary
internals. This compatibility runtime is declared explicitly rather than being
mistaken for the host source lock.

## pymbar

- Repository: https://github.com/choderalab/pymbar
- Commit: `ed40ec3bbef03bb08938ad1a74d459b0d1ab81f7`
- Tree: `da705aa87dd014f58741d74ceb08a19504cd1cb7`
- Source archive SHA-256:
  `d0e815a1bc88912cb0cb9c64bdb2ffc75eaec6f5225e79bd016acd5cbcf60a17`
- License: MIT.
- Role: study material in the Agent image and executable scientific reference
  in the private verifier. It never crosses the `/testbed` artifact boundary.

## Python wheels

The offline wheel sets are integrity checked against `SHA256SUMS` before
installation. They contain NumPy 2.3.2, SciPy 1.16.1, numexpr 2.14.1, and
OpenMM 8.5.2. No wheel is installed from the network during Harbor builds.

