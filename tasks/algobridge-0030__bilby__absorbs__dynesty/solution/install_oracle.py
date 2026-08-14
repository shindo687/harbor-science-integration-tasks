#!/usr/bin/env python3
"""Install the clean-room Oracle implementation into a Bilby checkout."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout", nargs="?", default="/testbed")
    args = parser.parse_args()
    root = Path(args.checkout).resolve()
    source = Path(__file__).resolve().parent
    destination = root / "bilby/core/sampler/internal_nested.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "internal_nested.py", destination)
    test_destination = root / "bilby/core/sampler/tests/test_internal_nested.py"
    test_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "internal_nested_test.py", test_destination)
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if '"bilby.internal_nested"' not in text:
        marker = '[project.entry-points."bilby.samplers"]\n'
        text = text.replace(
            marker,
            marker + '"bilby.internal_nested" = "bilby.core.sampler.internal_nested:InternalNested"\n',
            1,
        )
        pyproject.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

