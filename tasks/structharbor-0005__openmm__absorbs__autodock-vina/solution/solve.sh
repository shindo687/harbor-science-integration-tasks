#!/bin/sh
set -eu

install -m 0644 /solution/vina_score.py \
  /testbed/wrappers/python/openmm/app/vina_score.py
