#!/bin/sh
set -u

mkdir -p /logs/verifier
python /tests/grader.py
status=$?

if [ ! -s /logs/verifier/reward.txt ]; then
  printf '0\n' > /logs/verifier/reward.txt
fi

exit "$status"

