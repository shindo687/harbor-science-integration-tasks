#!/usr/bin/env python3
"""Create a plausible near miss by using Euclidean projected-cell chain weights."""

from __future__ import annotations

import argparse
from pathlib import Path


OLD = "chain_weight[position] <- abs(sum(from_point - projected[i, ]))"
NEW = "chain_weight[position] <- sqrt(sum((from_point - projected[i, ])^2))"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("testbed", type=Path)
    args = parser.parse_args()
    module = args.testbed / "R" / "principal_graph_pseudotime.R"
    text = module.read_text()
    if text.count(OLD) != 1:
        raise SystemExit("expected exact oracle chain-weight expression once")
    module.write_text(text.replace(OLD, NEW))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
