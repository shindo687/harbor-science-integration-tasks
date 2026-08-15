#!/usr/bin/env python3
"""Create a plausible near miss that omits the LPBE salt-screening term."""

from pathlib import Path


path = Path("/testbed/pdb2pqr/lpbe_grid.py")
text = path.read_text()
old = 'diagonal = diagonal + float(packet["zkappa2"]) * kappa[1:-1, 1:-1, 1:-1] * volume'
new = 'diagonal = diagonal + 0.0 * kappa[1:-1, 1:-1, 1:-1] * volume'
if text.count(old) != 1:
    raise SystemExit("expected solver expression was not found exactly once")
path.write_text(text.replace(old, new))
