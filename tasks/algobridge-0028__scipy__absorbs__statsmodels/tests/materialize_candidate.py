#!/usr/bin/env python3
"""Create a runnable exact-wheel SciPy tree with Candidate Python edits."""

from __future__ import annotations

import argparse
import importlib.metadata
from pathlib import Path
import shutil


def changed_python_files(testbed: Path, pristine: Path):
    for source in sorted((testbed / "scipy").rglob("*.py")):
        relative = source.relative_to(testbed)
        original = pristine / relative
        if not original.is_file() or source.read_bytes() != original.read_bytes():
            yield source, relative


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", default="/testbed")
    parser.add_argument("--pristine", default="/opt/pristine-host")
    parser.add_argument("--output", default="/opt/candidate-runtime")
    args = parser.parse_args()

    testbed = Path(args.testbed).resolve()
    pristine = Path(args.pristine).resolve()
    output = Path(args.output).resolve()
    distribution = importlib.metadata.distribution("scipy")
    installed = Path(distribution.locate_file("scipy")).resolve()
    if not (installed / "__init__.py").is_file():
        raise RuntimeError("the locked SciPy wheel is not installed")

    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(installed, output / "scipy")

    manifest = []
    for source, relative in changed_python_files(testbed, pristine):
        destination = output / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest.append(str(relative))
    (output / "OVERLAY-MANIFEST.txt").write_text(
        "\n".join(manifest) + ("\n" if manifest else "")
    )
    print(f"materialized {len(manifest)} changed Python files in {output}")


if __name__ == "__main__":
    main()

