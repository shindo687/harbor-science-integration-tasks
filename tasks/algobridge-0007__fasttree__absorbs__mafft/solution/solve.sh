#!/bin/sh
set -eu

test "$(sha256sum /testbed/FastTree.c | awk '{print $1}')" = \
  "975202a6b74c9996af871404ff043bb2152edcbda539035662514bc12d1f3431"
install -m 0644 /solution/AlignSmall.c /testbed/AlignSmall.c
install -m 0644 /solution/AlignSmall.h /testbed/AlignSmall.h
cd /testbed
python3 /solution/apply_fasttree.py
gcc -O3 -std=c99 -o FastTree FastTree.c AlignSmall.c -lm
