#!/bin/sh
set -eu
mkdir -p /logs/verifier
python /tests/grader.py
test -s /logs/verifier/reward.txt
