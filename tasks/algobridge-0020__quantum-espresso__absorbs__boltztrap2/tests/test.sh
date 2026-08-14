#!/bin/sh
set -u

mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt

if ! python3 /tests/grader.py; then
  printf '%s\n' '{"task":"ALGOBRIDGE-0020","status":"verifier_error","reward":0}' \
    > /logs/verifier/report.json
  printf '0\n' > /logs/verifier/reward.txt
fi

exit 0

