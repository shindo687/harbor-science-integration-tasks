#!/usr/bin/env python3
"""Create a wheel-backed sklearn tree overlaid with /testbed Python edits."""

from __future__ import annotations

import argparse
import importlib.metadata
import pathlib
import shutil


def changed_python_files(testbed, pristine):
    for source in sorted((testbed / "sklearn").rglob("*.py")):
        relative = source.relative_to(testbed)
        original = pristine / relative
        if not original.is_file() or source.read_bytes() != original.read_bytes():
            yield source, relative


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", default="/testbed")
    parser.add_argument("--pristine", default="/opt/pristine-host")
    parser.add_argument("--output", default="/tmp/candidate-runtime")
    args = parser.parse_args()
    testbed = pathlib.Path(args.testbed).resolve()
    pristine = pathlib.Path(args.pristine).resolve()
    output = pathlib.Path(args.output).resolve()
    distribution = importlib.metadata.distribution("scikit-learn")
    installed = pathlib.Path(distribution.locate_file("sklearn")).resolve()
    if output.exists():
        shutil.rmtree(output)
    shutil.copytree(installed, output / "sklearn")
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

