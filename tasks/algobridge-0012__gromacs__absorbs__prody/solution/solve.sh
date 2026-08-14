#!/bin/sh
set -eu
target=/testbed/python_packaging/gmxapi/src/gmxapi/analysis
mkdir -p "$target"
cp /solution/anm.py "$target/anm.py"
cp /solution/__init__.py "$target/__init__.py"
