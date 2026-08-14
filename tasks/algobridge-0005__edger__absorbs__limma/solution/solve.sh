#!/bin/sh
set -eu

test -d /testbed/R
test -f /testbed/NAMESPACE
test ! -e /testbed/R/voomFit.R

cp /solution/voomFit.R /testbed/R/voomFit.R
printf 'export(voomFit)\n' >> /testbed/NAMESPACE
