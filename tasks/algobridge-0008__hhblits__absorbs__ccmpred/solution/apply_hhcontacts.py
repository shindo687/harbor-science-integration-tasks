#!/usr/bin/env python3
"""Install the bounded native hhcontacts target into a pristine HH-suite tree."""

from pathlib import Path
import shutil
import sys


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_hhcontacts.py HH_SUITE_ROOT")
    root = Path(sys.argv[1]).resolve()
    source = Path(__file__).resolve().with_name("hhcontacts.cpp")
    destination = root / "src" / "hhcontacts.cpp"
    shutil.copyfile(source, destination)

    cmake = root / "src" / "CMakeLists.txt"
    text = cmake.read_text(encoding="utf-8")
    target_anchor = (
        "add_executable(hhconsensus${EXE_SUFFIX} hhconsensus.cpp)\n"
        "target_link_libraries(hhconsensus${EXE_SUFFIX} HH_OBJECTS)\n"
    )
    target_insert = target_anchor + (
        "\nadd_executable(hhcontacts${EXE_SUFFIX} hhcontacts.cpp)\n"
    )
    install_anchor = "        hhconsensus${EXE_SUFFIX}\n"
    install_insert = install_anchor + "        hhcontacts${EXE_SUFFIX}\n"
    if "add_executable(hhcontacts${EXE_SUFFIX}" in text:
        raise SystemExit("hhcontacts target already present")
    if text.count(target_anchor) != 1 or text.count(install_anchor) != 1:
        raise SystemExit("locked HH-suite CMake anchors not found exactly once")
    text = text.replace(target_anchor, target_insert)
    text = text.replace(install_anchor, install_insert)
    cmake.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
