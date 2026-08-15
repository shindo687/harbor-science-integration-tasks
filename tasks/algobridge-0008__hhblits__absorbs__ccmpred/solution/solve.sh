#!/bin/sh
set -eu
python3 /solution/apply_hhcontacts.py /testbed
g++ -std=c++11 -O3 -Wall -Wextra -pedantic /testbed/src/hhcontacts.cpp -o /testbed/hhcontacts
