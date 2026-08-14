# Verifier wheelhouse provenance

This directory is a complete, Python 3.10 Linux wheelhouse for the verifier's
locked AlphaFold/JAX runtime. `Dockerfile` installs it with `--no-index`, so a
Harbor cold build no longer depends on PyPI or Google Storage after the CUDA base
image and Ubuntu packages are available.

The dependency closure was resolved for CPython 3.10 on Ubuntu 22.04 from the
versions explicitly pinned in `tests/Dockerfile`; packages retain their upstream
licenses and metadata inside each wheel. `pdbfixer-1.12.0.tar.gz` is the upstream
source distribution because that release does not publish a Linux wheel; it is
built locally using the bundled build dependencies.

The CUDA closure also pins `nvidia-cuda-cupti-cu12==12.6.80` and
`nvidia-cuda-nvcc-cu12==12.6.85`. They supply CUPTI and `ptxas` missing from the
CUDA runtime base image and match the H200 runtime used by the real smoke test.

## CUDA JAXlib

`jaxlib-0.4.26+cuda12.cudnn89-cp310-cp310-manylinux2014_x86_64.whl`

- Version: JAXlib 0.4.26, CUDA 12, cuDNN 8.9
- Size: 144,167,766 bytes
- SHA256: `813cf1fe3e7ca4dbf5327d6e7b4fc8521e92d8bba073ee645ae0d5d036a25750`
- Upstream URL: `https://storage.googleapis.com/jax-releases/cuda12/jaxlib-0.4.26%2Bcuda12.cudnn89-cp310-cp310-manylinux2014_x86_64.whl`
- Upstream project license: Apache-2.0

The wheelhouse is verifier-only and is not copied into the Agent environment or
candidate artifact.
