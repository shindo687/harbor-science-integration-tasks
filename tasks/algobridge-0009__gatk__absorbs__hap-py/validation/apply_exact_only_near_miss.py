#!/usr/bin/env python3
"""Turn the oracle solution into a realistic literal-allele-only near miss."""

from __future__ import annotations

from pathlib import Path
import sys


RELATIVE = Path(
    "src/main/java/org/broadinstitute/hellbender/tools/walkers/variantutils/"
    "HaplotypeCompareVariants.java"
)


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
    path = root / RELATIVE
    text = path.read_text(encoding="utf-8")
    old = "&& haplotypesMatch(reference, referenceStart, truthBlock, queryBlock))"
    new = "&& false /* near miss: no haplotype equivalence */)"
    if text.count(old) != 1:
        raise SystemExit("expected oracle comparison expression exactly once")
    path.write_text(text.replace(old, new), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
