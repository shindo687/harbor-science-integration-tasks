#!/usr/bin/env python3
"""Install the clean-room Oracle implementation into /testbed."""

from __future__ import annotations

from pathlib import Path
import shutil


TESTBED = Path("/testbed")
SOURCE = Path("/solution/_batch_balanced.py")
DESTINATION = TESTBED / "src/scanpy/preprocessing/_batch_balanced.py"
INIT = TESTBED / "src/scanpy/preprocessing/__init__.py"


def main():
    if not TESTBED.is_dir() or not INIT.is_file():
        raise RuntimeError("/testbed is not the expected Scanpy source tree")
    shutil.copyfile(SOURCE, DESTINATION)
    text = INIT.read_text()
    import_line = "from ._batch_balanced import batch_balanced_neighbors\n"
    if import_line not in text:
        anchor = "from ._combat import combat\n"
        if anchor not in text:
            raise RuntimeError("could not locate preprocessing import anchor")
        text = text.replace(anchor, import_line + anchor, 1)
    export_line = '    "batch_balanced_neighbors",\n'
    if export_line not in text:
        anchor = '__all__ = [\n'
        if anchor not in text:
            raise RuntimeError("could not locate preprocessing __all__ anchor")
        text = text.replace(anchor, anchor + export_line, 1)
    INIT.write_text(text)
    print(f"installed Oracle into {DESTINATION}")


if __name__ == "__main__":
    main()

