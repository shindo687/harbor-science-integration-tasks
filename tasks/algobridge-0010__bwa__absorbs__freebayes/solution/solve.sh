#!/bin/sh
set -eu

cd /testbed
cp /solution/snv_call.c /solution/snv_call.h .

python3 - <<'PY'
from pathlib import Path

main = Path("main.c")
text = main.read_text(encoding="ascii")
text = text.replace('#include "utils.h"\n', '#include "utils.h"\n#include "snv_call.h"\n')
text = text.replace(
    'fprintf(stderr, "         mem           BWA-MEM algorithm\\n");',
    'fprintf(stderr, "         mem           BWA-MEM algorithm\\n");\n'
    'fprintf(stderr, "         snv-call      bounded biallelic SNV caller\\n");',
)
text = text.replace(
    'else if (strcmp(argv[1], "mem") == 0) ret = main_mem(argc-1, argv+1);',
    'else if (strcmp(argv[1], "mem") == 0) ret = main_mem(argc-1, argv+1);\n'
    '\telse if (strcmp(argv[1], "snv-call") == 0) ret = main_snv_call(argc-1, argv+1);',
)
main.write_text(text, encoding="ascii")

makefile = Path("Makefile")
text = makefile.read_text(encoding="ascii")
text = text.replace("AOBJS=\t\t", "AOBJS=\t\tsnv_call.o ")
makefile.write_text(text, encoding="ascii")
PY

make clean
make -j"$(nproc)"
