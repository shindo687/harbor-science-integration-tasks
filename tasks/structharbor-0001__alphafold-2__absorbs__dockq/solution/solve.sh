#!/usr/bin/env bash
set -euo pipefail
install -D -m 0644 /solution/oracle_impl.py "/testbed/alphafold/common/dockq_score.py"
python3 /solution/patch_run_alphafold.py /testbed/run_alphafold.py
