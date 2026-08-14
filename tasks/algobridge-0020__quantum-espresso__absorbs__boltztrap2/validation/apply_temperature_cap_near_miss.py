#!/usr/bin/env python3
"""Create a plausible but wrong implementation that caps T at 1000 K."""

from __future__ import annotations

import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    text = args.source.read_text()
    original = "kbt = temperatures_k(it) * boltzmann"
    replacement = "kbt = min(temperatures_k(it), 1000.0_dp) * boltzmann"
    if text.count(original) != 1:
        raise SystemExit("expected one temperature integration site")
    args.destination.parent.mkdir(parents=True, exist_ok=True)
    args.destination.write_text(text.replace(original, replacement))


if __name__ == "__main__":
    main()

