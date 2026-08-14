#!/usr/bin/env python3
"""Prepare the locked source snapshot as an installed editable Bilby tree."""

from pathlib import Path


PYPROJECT = Path("/testbed/pyproject.toml")


def main():
    text = PYPROJECT.read_text(encoding="utf-8")
    if '"bilby.internal_nested"' not in text:
        marker = '[project.entry-points."bilby.samplers"]\n'
        text = text.replace(
            marker,
            marker
            + '"bilby.internal_nested" = '
            + '"bilby.core.sampler.internal_nested:InternalNested"\n',
            1,
        )
    # setuptools-scm cannot derive a version after the curated snapshot has
    # intentionally dropped .git. A fallback preserves normal package metadata
    # while candidate changes still live directly under /testbed.
    if "fallback_version" not in text:
        text = text.replace(
            '[tool.setuptools_scm]\n',
            '[tool.setuptools_scm]\nfallback_version = "2.7.0rc0+locked.a139afa5"\n',
            1,
        )
    PYPROJECT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

