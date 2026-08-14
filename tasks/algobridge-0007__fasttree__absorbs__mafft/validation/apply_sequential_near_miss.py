#!/usr/bin/env python3
"""Create a calibrated wrong solution that merges the first active pair."""

from pathlib import Path
import sys


path = Path(sys.argv[1]) / "AlignSmall.c"
text = path.read_text()
old = """        if (as_pair_before(AS_DISTANCE(i, j), &clusters[i], &clusters[j],
                           best_distance,
                           best_i < 0 ? NULL : &clusters[best_i],
                           best_j < 0 ? NULL : &clusters[best_j])) {
"""
new = """        /* Deliberately wrong near miss: ignores all guide distances. */
        if (best_i < 0) {
"""
if text.count(old) != 1:
    raise SystemExit("near-miss anchor did not match exactly once")
path.write_text(text.replace(old, new, 1))

