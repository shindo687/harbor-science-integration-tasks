#!/usr/bin/env python3
"""Install an FC3 fit that omits crystallographic data augmentation."""

from pathlib import Path


SOURCE = Path("/solution/third_order.py")
TARGET = Path("/testbed/phonopy/harmonic/third_order.py")
OLD = """    augmented_u, augmented_f, operation_count = _augment(
        supercell, displacements, forces, is_symmetry, symprec
    )
"""
NEW = """    # Near miss: solve only the supplied snapshots and ignore the
    # crystallographic operations requested by is_symmetry.
    augmented_u, augmented_f, operation_count = displacements, forces, 1
"""


def main():
    text = SOURCE.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise RuntimeError("expected Oracle fitting block was not found once")
    TARGET.write_text(text.replace(OLD, NEW), encoding="utf-8")


if __name__ == "__main__":
    main()
