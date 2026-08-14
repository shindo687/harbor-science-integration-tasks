#!/usr/bin/env python3
"""Install a plausible but scientifically wrong uncentered-cosine solution."""

from __future__ import annotations

from pathlib import Path
import shutil
import sys


ROOT = Path(__file__).resolve().parents[1]
TESTBED = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")


def main() -> None:
    module = TESTBED / "src/scanpy/tools/_velocity_transition.py"
    regression = TESTBED / "src/scanpy/tools/test_velocity_transition.py"
    module.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "solution/_velocity_transition.py", module)
    shutil.copyfile(ROOT / "solution/test_velocity_transition.py", regression)

    text = module.read_text(encoding="utf-8")
    correct = "centered = displacement - np.mean(displacement, axis=1, keepdims=True)"
    wrong = "centered = displacement  # deliberate near miss: raw, uncentered displacement"
    if correct not in text:
        raise RuntimeError("Oracle source changed; near-miss mutation is stale")
    module.write_text(text.replace(correct, wrong, 1), encoding="utf-8")

    init = TESTBED / "src/scanpy/tools/__init__.py"
    text = init.read_text(encoding="utf-8")
    import_line = "from ._velocity_transition import velocity_transition_graph\n"
    if import_line not in text:
        text = text.replace("from ._umap import umap\n", "from ._umap import umap\n" + import_line, 1)
    export_line = '    "velocity_transition_graph",\n'
    if export_line not in text:
        text = text.replace('    "umap",\n', '    "umap",\n' + export_line, 1)
    init.write_text(text, encoding="utf-8")
    print("installed deliberate uncentered-cosine near miss")


if __name__ == "__main__":
    main()
