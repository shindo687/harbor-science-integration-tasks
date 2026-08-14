#!/usr/bin/env python3
"""Overlay the two permitted candidate files onto the locked sklearn wheel."""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
import shutil


ALLOWED = (
    Path("sklearn/ensemble/__init__.py"),
    Path("sklearn/ensemble/_second_order_gradient_boosting.py"),
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", default="/testbed")
    parser.add_argument("--output", default="/tmp/candidate-runtime")
    args = parser.parse_args()
    testbed = Path(args.testbed).resolve()
    output = Path(args.output).resolve()
    installed = Path(
        importlib.metadata.distribution("scikit-learn").locate_file("sklearn")
    ).resolve()
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(installed, output / "sklearn")
    copied = []
    for relative in ALLOWED:
        source = testbed / relative
        if source.is_file():
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            copied.append(str(relative))
    (output / "OVERLAY-MANIFEST.txt").write_text(
        "\n".join(copied) + ("\n" if copied else ""), encoding="utf-8"
    )
    print(f"materialized {len(copied)} candidate files in {output}")


if __name__ == "__main__":
    main()
