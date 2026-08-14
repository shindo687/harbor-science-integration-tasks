#!/bin/sh
set -eu

solution_dir=${SOLUTION_DIR:-/solution}
testbed_dir=${TESTBED_DIR:-/testbed}
export TESTBED_DIR="$testbed_dir"

cp "$solution_dir/gmx_dssp_internal.cpp" \
  "$testbed_dir/src/gromacs/gmxana/gmx_dssp_internal.cpp"

python3 - <<'PY'
import os
from pathlib import Path

path = Path(os.environ["TESTBED_DIR"]) / "src/programs/legacymodules.cpp"
text = path.read_text()
declaration_anchor = '#include "legacymodules.h"\n'
declaration = '\nint gmx_dssp_internal(int argc, char* argv[]);\n'
registration_anchor = '''    registerModule(manager, &gmx_analyze, "analyze", "Analyze data sets");
'''
registration = registration_anchor + '''    registerModule(manager,
                   &gmx_dssp_internal,
                   "dssp-internal",
                   "Assign bounded native DSSP secondary structure across frames");
'''
if declaration not in text:
    if declaration_anchor not in text:
        raise SystemExit("declaration anchor missing")
    text = text.replace(declaration_anchor, declaration_anchor + declaration, 1)
if '"dssp-internal"' not in text:
    if registration_anchor not in text:
        raise SystemExit("registration anchor missing")
    text = text.replace(registration_anchor, registration, 1)
path.write_text(text)
PY
