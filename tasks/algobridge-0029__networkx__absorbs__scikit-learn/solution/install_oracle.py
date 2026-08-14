#!/usr/bin/env python3
"""Install the author Oracle into the locked NetworkX checkout."""

from __future__ import annotations

import pathlib
import shutil
import sys

testbed = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
source = (
    pathlib.Path(sys.argv[2])
    if len(sys.argv) > 2
    else pathlib.Path(__file__).with_name("spectral.py")
)
target = testbed / "networkx/algorithms/community/spectral.py"
target.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(source, target)

community_init = testbed / "networkx/algorithms/community/__init__.py"
community_line = "from networkx.algorithms.community.spectral import *\n"
text = community_init.read_text()
if community_line not in text:
    community_init.write_text(text + community_line)

algorithms_init = testbed / "networkx/algorithms/__init__.py"
algorithm_line = "from networkx.algorithms.community.spectral import spectral_clustering\n"
text = algorithms_init.read_text()
if algorithm_line not in text:
    algorithms_init.write_text(text + "\n" + algorithm_line)
