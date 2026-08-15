#!/usr/bin/env python3
"""Protected reference adapter for interface-energy-lite packets."""

from __future__ import annotations

import json
import sys

from reference_impl import score_interface


json.dump(score_interface(json.load(sys.stdin)), sys.stdout, allow_nan=False,
          separators=(",", ":"))
sys.stdout.write("\n")
