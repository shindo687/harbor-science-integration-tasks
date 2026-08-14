#!/usr/bin/env bash
set -euo pipefail

mkdir -p /logs/verifier
finish() {
  code="$?"
  trap - EXIT
  if [ ! -s /logs/verifier/reward.txt ]; then
    echo 0 > /logs/verifier/reward.txt
  fi
  exit "$code"
}
trap finish EXIT

python3 /tests/grader.py 2>&1 | tee /logs/verifier/grader.log
test -s /logs/verifier/reward.txt
test -s /logs/verifier/report.json
