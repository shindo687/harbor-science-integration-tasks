#!/bin/sh
set -eu

test -d /testbed/R
test -f /testbed/NAMESPACE
test ! -e /testbed/R/enrichment.R

cp /solution/enrichment.R /testbed/R/enrichment.R
printf 'export(EnrichMarkers)\n' >> /testbed/NAMESPACE
