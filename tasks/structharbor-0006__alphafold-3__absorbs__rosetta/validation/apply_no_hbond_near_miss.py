#!/usr/bin/env python3
"""Acceptance control: remove the orientation-aware H-bond contribution."""

from pathlib import Path


path = Path("/testbed/src/alphafold3/model/interface_energy_lite.py")
text = path.read_text()
needle = "return (-parameters[\"hbond_strength\"] * radial * donor_cosine ** 2\n            * acceptor_cosine ** 2 * scale)"
replacement = "return 0.0  # deliberate near miss: H-bond term omitted"
if text.count(needle) != 1:
    raise SystemExit("near-miss patch target not found exactly once")
path.write_text(text.replace(needle, replacement))
