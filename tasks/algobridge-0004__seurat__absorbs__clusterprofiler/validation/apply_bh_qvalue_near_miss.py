#!/usr/bin/env python3
"""Replace Storey q-values with plain BH values in a solved candidate tree."""

from pathlib import Path
import sys


root = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
path = root / "R" / "enrichment.R"
text = path.read_text(encoding="utf-8")
start_marker = "  pi_zero <- min(1, mean(p >= 0.05) / 0.95)\n"
end_marker = "\n\n  descriptions <- terms\n"
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit("expected Oracle q-value block was not found")
replacement = "  q <- as.double(p.adjust(p, method = \"BH\"))"
path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")

