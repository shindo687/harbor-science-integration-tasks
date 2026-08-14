#!/bin/sh
set -eu

install -m 0644 /solution/principal_graph_pseudotime.R \
  /testbed/R/principal_graph_pseudotime.R

if ! grep -qxF 'export(PrincipalGraphPseudotime)' /testbed/NAMESPACE; then
  printf 'export(PrincipalGraphPseudotime)\n' >> /testbed/NAMESPACE
fi

if ! grep -qxF "    'principal_graph_pseudotime.R'" /testbed/DESCRIPTION; then
  sed -i "/^    'tree.R'$/i\\    'principal_graph_pseudotime.R'" \
    /testbed/DESCRIPTION
fi

grep -qxF 'export(PrincipalGraphPseudotime)' /testbed/NAMESPACE
grep -qxF "    'principal_graph_pseudotime.R'" /testbed/DESCRIPTION
