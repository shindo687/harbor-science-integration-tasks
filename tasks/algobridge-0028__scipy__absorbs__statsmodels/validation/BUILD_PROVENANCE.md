# Build provenance

The source roots were checked out at the commits in `source-lock.json`.
SciPy's eight gitlinks were initialized at their locked commits before the
source snapshot and wheel were produced.

Both wheels were built for CPython 3.12.11 on Debian bookworm with
`python -m pip wheel --no-deps`, Meson, GCC/GFortran 12, and Debian OpenBLAS.

- `scipy-2.0.0.dev0-cp312-cp312-linux_x86_64.whl`
  - SHA-256: `669eac7a6b24b5a825d2e9a19b40d750f740e45f4ae186bc8e4ff9304e56b2d0`
- `statsmodels-0.15.0.dev1982+g9062763c8-cp312-cp312-linux_x86_64.whl`
  - SHA-256: `8bf1e5fee15b7bd26b34db7513786e734c9f680f7edf65437ab65c50d61b3dc9`

The final Agent and verifier images install only repository-carried wheels and
Debian runtime packages with `--network=none`. `ldd` over the installed SciPy
extensions reported no missing shared libraries, and the exact reference
imported as SciPy `2.0.0.dev0` plus statsmodels
`0.15.0.dev1982+g9062763c8`.

