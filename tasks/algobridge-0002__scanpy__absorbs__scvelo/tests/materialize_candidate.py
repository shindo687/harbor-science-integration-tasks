#!/usr/bin/env python3
"""Overlay changed candidate Scanpy Python files on the exact wheel install."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--testbed", default="/testbed")
    parser.add_argument("--pristine", default="/opt/pristine-host")
    parser.add_argument("--installed", default="/opt/installed-scanpy")
    parser.add_argument("--output", default="/opt/candidate-runtime")
    args = parser.parse_args()
    testbed, pristine = Path(args.testbed), Path(args.pristine)
    installed, output = Path(args.installed), Path(args.output)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    shutil.copytree(installed / "scanpy", output / "scanpy")
    if (installed / "testing").is_dir():
        shutil.copytree(installed / "testing", output / "testing")
    manifest = []
    for source in sorted((testbed / "src/scanpy").rglob("*.py")):
        relative = source.relative_to(testbed)
        original = pristine / relative
        if original.is_file() and source.read_bytes() == original.read_bytes():
            continue
        destination = output / relative.relative_to("src")
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        manifest.append(str(relative))
    (output / "OVERLAY-MANIFEST.txt").write_text(
        "\n".join(manifest) + ("\n" if manifest else ""), encoding="utf-8"
    )
    print(f"materialized {len(manifest)} changed Python files")


if __name__ == "__main__":
    main()
