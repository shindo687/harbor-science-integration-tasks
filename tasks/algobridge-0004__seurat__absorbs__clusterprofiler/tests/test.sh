#!/bin/sh
set -u

mkdir -p /logs/verifier
printf '0\n' > /logs/verifier/reward.txt

if ! Rscript /tests/grader.R; then
  printf '%s\n' '{"task_id":"ALGOBRIDGE-0004","status":"verifier_error","reward":0}' \
    > /logs/verifier/report.json
  printf '0\n' > /logs/verifier/reward.txt
fi

exit 0

