#!/usr/bin/env python3
"""Install a plausible GNM-correct but scientifically wrong ANM solution."""

from pathlib import Path


SOURCE = Path("/solution/normal_modes.py")
TARGET = Path("/testbed/alphafold/common/normal_modes.py")
START = "def _hessian("
END = "\ndef _mode_statistics("
REPLACEMENT = '''def _hessian(coordinates, cutoff, gamma):
    """Near miss: isotropic Cartesian springs, not directional ANM."""
    kirchhoff = _kirchhoff(coordinates, cutoff, gamma)
    return np.kron(kirchhoff, np.eye(3, dtype=float))
'''


def main():
    text = SOURCE.read_text(encoding="utf-8")
    begin = text.index(START)
    finish = text.index(END, begin)
    TARGET.write_text(text[:begin] + REPLACEMENT + text[finish:], encoding="utf-8")


if __name__ == "__main__":
    main()
