#!/usr/bin/env python3
"""Install a plausible but scientifically wrong count-symmetrization solution."""

from pathlib import Path


SOURCE = Path("/solution/markov_model.py")
TARGET = Path("/testbed/wrappers/python/openmm/app/markov_model.py")
INIT = Path("/testbed/wrappers/python/openmm/app/__init__.py")
START = "def _reversible_transition_matrix("
END = "\ndef _stationary_distribution("
REPLACEMENT = '''def _reversible_transition_matrix(counts, tolerance=1e-13, maximum_iterations=1000000):
    """Near miss: row-normalize symmetrized counts instead of solving the MLE."""
    del tolerance, maximum_iterations
    symmetric = np.asarray(counts, dtype=float) + np.asarray(counts, dtype=float).T
    row_sums = symmetric.sum(axis=1)
    transition = symmetric / row_sums[:, None]
    stationary = row_sums / row_sums.sum()
    return transition, stationary
'''


def main():
    text = SOURCE.read_text(encoding="utf-8")
    begin = text.index(START)
    finish = text.index(END, begin)
    TARGET.write_text(text[:begin] + REPLACEMENT + text[finish:], encoding="utf-8")
    init_text = INIT.read_text(encoding="utf-8")
    export = "from .markov_model import estimate_markov_model\n"
    if export not in init_text:
        init_text += "\n" + export
    INIT.write_text(init_text, encoding="utf-8")


if __name__ == "__main__":
    main()

