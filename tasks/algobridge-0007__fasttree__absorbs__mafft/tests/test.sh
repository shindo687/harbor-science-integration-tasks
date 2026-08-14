#!/bin/bash
set -euo pipefail

mkdir -p /logs/verifier
python3 /tests/grader.py 2>&1 | tee /logs/verifier/grader.log
test -s /logs/verifier/reward.txt
test -s /logs/verifier/report.json

