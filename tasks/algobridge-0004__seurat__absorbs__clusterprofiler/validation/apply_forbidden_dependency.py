#!/usr/bin/env python3
"""Inject a dormant forbidden donor call to exercise the dependency gate."""

from pathlib import Path
import sys


root = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
path = root / "R" / "enrichment.R"
text = path.read_text(encoding="utf-8")
text += "\nif (FALSE) clusterProfiler::enricher(character(), TERM2GENE=data.frame())\n"
path.write_text(text, encoding="utf-8")

