#!/bin/sh
set -eu
mkdir -p /logs/verifier
python3 /tests/grader.py
test -s /logs/verifier/reward.txt

