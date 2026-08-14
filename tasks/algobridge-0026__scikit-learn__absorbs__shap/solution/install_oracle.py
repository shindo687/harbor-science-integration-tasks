#!/usr/bin/env python3
"""Install the clean-room author Oracle into the locked host checkout."""

from __future__ import annotations

import pathlib
import shutil
import sys


testbed = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
source = pathlib.Path(__file__).with_name("_tree_shap.py")
target = testbed / "sklearn/inspection/_tree_shap.py"
shutil.copyfile(source, target)
shutil.copyfile(
    pathlib.Path(__file__).with_name("test_tree_shap.py"),
    testbed / "sklearn/inspection/tests/test_tree_shap.py",
)

init_path = testbed / "sklearn/inspection/__init__.py"
text = init_path.read_text()
import_line = "from sklearn.inspection._tree_shap import tree_shap\n"
if import_line not in text:
    marker = "from sklearn.inspection._permutation_importance import permutation_importance\n"
    text = text.replace(marker, marker + import_line)
if '    "tree_shap",\n' not in text:
    text = text.replace('    "permutation_importance",\n', '    "permutation_importance",\n    "tree_shap",\n')
init_path.write_text(text)
