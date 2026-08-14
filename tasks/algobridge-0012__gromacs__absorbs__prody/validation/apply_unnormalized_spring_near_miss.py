#!/usr/bin/env python3
"""Install a directional network with the ANM distance normalization omitted."""

from pathlib import Path


SOURCE = Path("/solution/anm.py")
TARGET = Path("/testbed/python_packaging/gmxapi/src/gmxapi/analysis/anm.py")
INIT_SOURCE = Path("/solution/__init__.py")
INIT_TARGET = Path(
    "/testbed/python_packaging/gmxapi/src/gmxapi/analysis/__init__.py"
)
OLD = "block = -gamma * np.outer(difference, difference) / distance_squared"
NEW = "block = -gamma * np.outer(difference, difference)"


def main():
    text = SOURCE.read_text(encoding="utf-8")
    if text.count(OLD) != 1:
        raise RuntimeError("expected normalized spring expression was not found once")
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(text.replace(OLD, NEW), encoding="utf-8")
    INIT_TARGET.write_text(INIT_SOURCE.read_text(encoding="utf-8"), encoding="utf-8")


if __name__ == "__main__":
    main()
