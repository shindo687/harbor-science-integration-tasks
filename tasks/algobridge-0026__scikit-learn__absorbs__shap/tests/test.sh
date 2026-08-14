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
python /tests/grader.py

