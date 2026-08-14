#!/bin/sh
set -eu

install -d /testbed/PP/src
install -m 0644 /solution/transport_moments.f90 \
  /testbed/PP/src/transport_moments.f90

