#!/usr/bin/env bash
set -euo pipefail

testbed="${1:-/testbed}"
install -D -m 0644 \
  /solution/complex_metrics.py \
  "$testbed/colabfold/alphafold/complex_metrics.py"
python3 /solution/patch_batch.py "$testbed/colabfold/batch.py"
