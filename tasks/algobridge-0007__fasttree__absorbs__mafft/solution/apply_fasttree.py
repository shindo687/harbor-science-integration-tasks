#!/usr/bin/env python3
"""Apply the small integration seam to the locked FastTree.c exactly once."""

from pathlib import Path


path = Path("/testbed/FastTree.c")
text = path.read_text()


def replace_once(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"cannot apply {label}: expected one anchor, found {count}")
    text = text.replace(old, new, 1)


replace_once(
    '#include <unistd.h>\n',
    '#include <unistd.h>\n#include "AlignSmall.h"\n',
    "header include",
)
replace_once(
    "  FILE *fpOut = stdout;\n",
    """  FILE *fpOut = stdout;
  bool alignSmall = false;
  char *alignmentOut = NULL;
  char *guideTreeOut = NULL;
  char *alignMatrix = NULL;
  double alignGapOpen = 4.0;
  double alignGapExtend = 0.75;
""",
    "alignment option state",
)
replace_once(
    """  for (iArg = 1; iArg < argc; iArg++) {
    if (strcmp(argv[iArg],"-makematrix") == 0) {
""",
    """  for (iArg = 1; iArg < argc; iArg++) {
    if (strcmp(argv[iArg], "--align-small") == 0) {
      alignSmall = true;
    } else if (strcmp(argv[iArg], "--alignment-out") == 0 && iArg < argc-1) {
      alignmentOut = argv[++iArg];
    } else if (strcmp(argv[iArg], "--guide-tree-out") == 0 && iArg < argc-1) {
      guideTreeOut = argv[++iArg];
    } else if (strcmp(argv[iArg], "--align-matrix") == 0 && iArg < argc-1) {
      alignMatrix = argv[++iArg];
    } else if (strcmp(argv[iArg], "--align-gap-open") == 0 && iArg < argc-1) {
      alignGapOpen = strtod(argv[++iArg], NULL);
    } else if (strcmp(argv[iArg], "--align-gap-extend") == 0 && iArg < argc-1) {
      alignGapExtend = strtod(argv[++iArg], NULL);
    } else if (strcmp(argv[iArg],"-makematrix") == 0) {
""",
    "command-line parser",
)
replace_once(
    "  char *fileName = iArg == (argc-1) ?  argv[argc-1] : NULL;\n",
    """  char *fileName = iArg == (argc-1) ?  argv[argc-1] : NULL;

  if (alignSmall) {
    if (fileName == NULL || alignmentOut == NULL || guideTreeOut == NULL
        || alignMatrix == NULL || nAlign != 1) {
      fprintf(stderr, "--align-small requires an input file, --alignment-out, "
              "--guide-tree-out, and --align-matrix\\n");
      exit(1);
    }
    if (AlignSmallFasta(fileName, alignmentOut, guideTreeOut, nCodes == 4,
                        alignMatrix, alignGapOpen, alignGapExtend) != 0)
      exit(1);
    fileName = alignmentOut;
  }
""",
    "alignment dispatch",
)

path.write_text(text)

