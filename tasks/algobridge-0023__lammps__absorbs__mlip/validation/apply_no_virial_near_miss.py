#!/usr/bin/env python3
"""Create a scientifically incomplete candidate that omits global virial tallying."""

from pathlib import Path


path = Path("/testbed/src/pair_mtp_bounded.cpp")
text = path.read_text(encoding="utf-8")
needle = "  if (vflag_fdotr) virial_fdotr_compute();\n"
if text.count(needle) != 1:
    raise SystemExit("expected one global virial tally call")
path.write_text(text.replace(needle, "  // near miss: global virial tally omitted\n"), encoding="utf-8")

