#!/bin/sh
set -eu
mkdir -p /logs/verifier
Rscript /tests/grader.R
test -s /logs/verifier/reward.txt
