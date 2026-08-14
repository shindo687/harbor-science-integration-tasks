#!/usr/bin/env python3
"""Create an immutable OpenMM runtime containing only the submitted module."""

from pathlib import Path
import shutil


TESTBED = Path("/testbed")
SOURCE = TESTBED / "wrappers/python/openmm/app/markov_model.py"
SOURCE_INIT = TESTBED / "wrappers/python/openmm/app/__init__.py"
BASE = Path("/opt/installed-openmm/openmm")
BASE_LIBS = Path("/opt/installed-openmm/OpenMM.libs")
TARGET_ROOT = Path("/opt/candidate-runtime")
TARGET = TARGET_ROOT / "openmm"
EXPORT = "from .markov_model import estimate_markov_model"


def main():
    if not SOURCE.is_file():
        raise SystemExit("missing wrappers/python/openmm/app/markov_model.py")
    if EXPORT not in SOURCE_INIT.read_text(encoding="utf-8"):
        raise SystemExit(f"missing public export: {EXPORT}")
    if TARGET_ROOT.exists():
        shutil.rmtree(TARGET_ROOT)
    shutil.copytree(BASE, TARGET)
    shutil.copytree(BASE_LIBS, TARGET_ROOT / "OpenMM.libs")
    shutil.copy2(SOURCE, TARGET / "app/markov_model.py")
    runtime_init = TARGET / "app/__init__.py"
    with runtime_init.open("a", encoding="utf-8") as handle:
        handle.write("\n" + EXPORT + "\n")
    (TARGET_ROOT / "OVERLAY-MANIFEST.txt").write_text(
        "wrappers/python/openmm/app/markov_model.py -> openmm/app/markov_model.py\n"
        "wrappers/python/openmm/app/__init__.py -> public export\n",
        encoding="utf-8",
    )
    for path in [TARGET_ROOT, *TARGET_ROOT.rglob("*")]:
        path.chmod(0o555 if path.is_dir() else 0o444)


if __name__ == "__main__":
    main()

