#!/usr/bin/env python3
"""Install the API-only near miss into a validation checkout."""

from __future__ import annotations

import pathlib
import shutil
import sys


testbed = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
shutil.copyfile(pathlib.Path(__file__).with_name("near_miss.py"), testbed / "sklearn/preprocessing/_smote.py")
init_path = testbed / "sklearn/preprocessing/__init__.py"
text = init_path.read_text()
import_line = "from sklearn.preprocessing._smote import SMOTE\n"
if import_line not in text:
    marker = "from sklearn.preprocessing._polynomial import PolynomialFeatures, SplineTransformer\n"
    text = text.replace(marker, marker + import_line)
if '    "SMOTE",\n' not in text:
    text = text.replace('    "RobustScaler",\n', '    "RobustScaler",\n    "SMOTE",\n')
init_path.write_text(text)
