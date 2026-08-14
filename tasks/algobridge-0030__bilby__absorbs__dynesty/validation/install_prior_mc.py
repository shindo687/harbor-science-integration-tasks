#!/usr/bin/env python3
from pathlib import Path
import argparse
import shutil


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("checkout")
    args = parser.parse_args()
    root = Path(args.checkout)
    target = root / "bilby/core/sampler/internal_nested.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name("prior_mc.py"), target)
    tests = root / "bilby/core/sampler/tests/test_internal_nested.py"
    tests.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).parents[1] / "solution/internal_nested_test.py", tests)
    pyproject = root / "pyproject.toml"
    text = pyproject.read_text()
    marker = '[project.entry-points."bilby.samplers"]\n'
    if '"bilby.internal_nested"' not in text:
        text = text.replace(marker, marker + '"bilby.internal_nested" = "bilby.core.sampler.internal_nested:InternalNested"\n', 1)
        pyproject.write_text(text)


if __name__ == "__main__":
    main()

