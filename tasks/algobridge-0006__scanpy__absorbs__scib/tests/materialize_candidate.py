#!/usr/bin/env python3
"""Overlay Candidate Python edits on the exact installed Scanpy wheel."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def changed_python_files(testbed, pristine):
    source_root = testbed / "src/scanpy"
    for source in sorted(source_root.rglob("*.py")):
        relative = source.relative_to(testbed)
        original = pristine / relative
        if not original.is_file() or source.read_bytes() != original.read_bytes():
            yield source, relative


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", default="/testbed")
    parser.add_argument("--pristine", default="/opt/pristine-host")
    parser.add_argument("--installed", default="/opt/installed-scanpy")
    parser.add_argument("--output", default="/opt/candidate-runtime")
    args = parser.parse_args()
    testbed = Path(args.testbed).resolve()
    pristine = Path(args.pristine).resolve()
    installed = Path(args.installed).resolve()
    output = Path(args.output).resolve()
    if not (installed / "scanpy/__init__.py").is_file():
        raise RuntimeError("the exact installed Scanpy package is missing")
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    shutil.copytree(installed / "scanpy", output / "scanpy")
    if (installed / "testing").is_dir():
        shutil.copytree(installed / "testing", output / "testing")
    manifest = []
    for source, relative in changed_python_files(testbed, pristine):
        destination = output / relative.relative_to("src")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest.append(str(relative))
    (output / "OVERLAY-MANIFEST.txt").write_text(
        "\n".join(manifest) + ("\n" if manifest else "")
    )
    print(f"materialized {len(manifest)} changed Python files in {output}")


if __name__ == "__main__":
    main()

