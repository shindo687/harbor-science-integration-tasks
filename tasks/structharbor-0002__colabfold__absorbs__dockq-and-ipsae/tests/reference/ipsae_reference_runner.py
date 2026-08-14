#!/usr/bin/env python3
"""Run the locked ipSAE v4 script and convert its AF2 table to JSON."""
from __future__ import annotations

import json
import math
import subprocess
import sys
from pathlib import Path


SCRIPT, SCORES, MODEL, OUTPUT = map(Path, sys.argv[1:5])
PAE_CUTOFF = float(sys.argv[5])
DISTANCE_CUTOFF = float(sys.argv[6])

completed = subprocess.run(
    [
        sys.executable,
        str(SCRIPT),
        str(SCORES),
        str(MODEL),
        str(PAE_CUTOFF),
        str(DISTANCE_CUTOFF),
    ],
    text=True,
    capture_output=True,
    check=False,
)
if completed.returncode:
    raise SystemExit(
        f"locked ipSAE failed ({completed.returncode}):\n"
        f"{completed.stderr}\n{completed.stdout}"
    )

pae_token = str(int(PAE_CUTOFF)).zfill(2)
distance_token = str(int(DISTANCE_CUTOFF)).zfill(2)
table_path = MODEL.with_suffix("")
table_path = Path(f"{table_path}_{pae_token}_{distance_token}.txt")
if not table_path.exists():
    raise SystemExit(f"locked ipSAE did not create {table_path}")

records = []


def d0(length):
    if length > 27:
        return max(1.0, 1.24 * (float(length) - 15.0) ** (1.0 / 3.0) - 1.8)
    return 1.0


for raw_line in table_path.read_text(encoding="utf-8").splitlines():
    fields = raw_line.split()
    if len(fields) != 24 or fields[0] == "Chn1":
        continue
    records.append(
        {
            "chain1": fields[0],
            "chain2": fields[1],
            "type": fields[4],
            "ipsae": float(fields[5]),
            "ipsae_d0chn": float(fields[6]),
            "ipsae_d0dom": float(fields[7]),
            "iptm_af": float(fields[8]),
            "iptm_d0chn": float(fields[9]),
            "pdockq": float(fields[10]),
            "pdockq2": float(fields[11]),
            "lis": float(fields[12]),
            "n0res": int(fields[13]),
            "n0chn": int(fields[14]),
            "n0dom": int(fields[15]),
            # The human table rounds d0 to two decimals. Reconstruct the exact
            # protein d0 from donor-emitted n0 values for differential grading.
            "d0res": d0(int(fields[13])),
            "d0chn": d0(int(fields[14])),
            "d0dom": d0(int(fields[15])),
            "nres1": int(fields[19]),
            "nres2": int(fields[20]),
            "dist1": int(fields[21]),
            "dist2": int(fields[22]),
        }
    )

payload = {
    "pae_cutoff": PAE_CUTOFF,
    "distance_cutoff": DISTANCE_CUTOFF,
    "chain_pairs": records,
}
OUTPUT.write_text(
    json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n",
    encoding="utf-8",
)
print(json.dumps(payload, sort_keys=True, allow_nan=False))
