#!/usr/bin/env python3
"""Create a read-only sklearn runtime containing only permitted overlays."""

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
    parser.add_argument("--output", default="/opt/candidate-runtime")
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
        if not source.is_file():
            raise FileNotFoundError(relative)
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        copied.append(str(relative))
    (output / "OVERLAY-MANIFEST.txt").write_text(
        "\n".join(copied) + "\n", encoding="utf-8"
    )
    shutil.copymode(installed, output / "sklearn")
    print(f"materialized {len(copied)} candidate files")


if __name__ == "__main__":
    main()
