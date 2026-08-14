#!/usr/bin/env python3
"""Turn the accepted Oracle into a plausible covariance-only near miss."""

from pathlib import Path


path = Path("/testbed/wrappers/python/openmm/app/mbar.py")
with path.open("a", encoding="utf-8") as handle:
    handle.write(
        "\n\n# Deliberate near miss: the Kong approximation underestimates MBAR error.\n"
        "def _covariance(weights, counts):\n"
        "    gram = weights.T @ weights\n"
        "    return 0.5 * (gram + gram.T)\n"
    )

