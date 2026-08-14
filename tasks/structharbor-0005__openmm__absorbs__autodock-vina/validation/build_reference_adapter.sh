#!/bin/sh
set -eu

if [ "$#" -ne 2 ]; then
  echo "usage: $0 /path/to/AutoDock-Vina /output/path" >&2
  exit 2
fi

donor_root=$1
output=$2
repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

g++ -std=c++17 -O2 -DNDEBUG \
  -I "$repo_root/tests/reference-compat" \
  -I "$donor_root/src/lib" \
  "$repo_root/tests/reference_adapter.cpp" \
  -o "$output"
