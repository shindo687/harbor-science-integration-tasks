#!/usr/bin/env python3
"""Create a realistic near miss that forgets CCMpred's (L-1) L2 scaling."""

from pathlib import Path
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_regularization_near_miss.py HH_SUITE_ROOT")
    path = Path(sys.argv[1]) / "src" / "hhcontacts.cpp"
    text = path.read_text(encoding="utf-8")
    old = "pair_lambda_(pair_factor * (length_ - 1)), evaluations_(0)"
    new = "pair_lambda_(pair_factor * (length_ - 2)), evaluations_(0)"
    if text.count(old) != 1:
        raise SystemExit("locked regularization expression not found exactly once")
    path.write_text(text.replace(old, new), encoding="utf-8")


if __name__ == "__main__":
    main()
