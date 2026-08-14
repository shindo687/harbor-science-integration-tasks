#!/usr/bin/env python3
"""Install an intentionally incomplete candidate into a Harbor artifact."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    destination = args.artifact.resolve() / "src"
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copy2(repository / "solution/fit_harmonic_fc2.h", destination / "fit_harmonic_fc2.h")
    source = (repository / "solution/fit_harmonic_fc2.cpp").read_text(encoding="utf-8")
    needle = "  symmetrize(fc, input.iterations);"
    if source.count(needle) != 1:
        raise RuntimeError("Oracle projection call changed; near miss is stale")
    source = source.replace(needle, "  /* Intentionally omit the constraint projection. */")
    (destination / "fit_harmonic_fc2.cpp").write_text(source, encoding="utf-8")


if __name__ == "__main__":
    main()
