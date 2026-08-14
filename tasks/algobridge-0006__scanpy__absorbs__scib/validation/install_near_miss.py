#!/usr/bin/env python3
"""Install an intentionally incomplete, uniform-neighborhood LISI solution."""

from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parents[1]
testbed = Path(sys.argv[1] if len(sys.argv) > 1 else "/testbed")
subprocess.run(
    [
        sys.executable,
        str(root / "solution/install_oracle.py"),
        str(testbed),
        str(root / "solution/_lisi.py"),
    ],
    check=True,
)
target = testbed / "src/scanpy/metrics/_lisi.py"
text = target.read_text()
needle = """    target = math.log(perplexity)\n    beta = 1.0\n"""
replacement = """    # Deliberately wrong: ignore distances and the requested perplexity.\n    return np.full(len(distances), 1.0 / len(distances), dtype=np.float64)\n\n    target = math.log(perplexity)\n    beta = 1.0\n"""
if needle not in text:
    raise RuntimeError("Oracle source layout changed; near-miss is stale")
target.write_text(text.replace(needle, replacement, 1))

