#!/usr/bin/env python3
"""Root-only adapter around the locked official MLIP-3 executable."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from cases import validate_case


REFERENCE = Path(os.environ.get("MLIP_REFERENCE_BIN", "/opt/reference-mlip/bin/mlp"))
LIBRARIES = Path(os.environ.get("MLIP_REFERENCE_LIB", "/opt/reference-mlip/lib"))
POTENTIAL = Path(os.environ.get("MTP_BOUNDED_POTENTIAL", "/opt/reference-mlip/mtp9-bounded.mtp"))


def _write_cfg(path, packet):
    lx, ly, lz = packet["box"]
    lines = [
        "BEGIN_CFG", " Size", f"    {len(packet['positions'])}", " Supercell",
        f"    {lx:.16e} 0.0 0.0", f"    0.0 {ly:.16e} 0.0",
        f"    0.0 0.0 {lz:.16e}",
        " AtomData: id type cartes_x cartes_y cartes_z",
    ]
    for index, point in enumerate(packet["positions"], 1):
        lines.append(f"    {index} 0 {point[0]:.16e} {point[1]:.16e} {point[2]:.16e}")
    lines.append("END_CFG")
    path.write_text("\n".join(lines) + "\n", encoding="ascii")


def _parse_cfg(path, count):
    lines = path.read_text(encoding="utf-8").splitlines()
    atom_line = next(index for index, line in enumerate(lines) if line.strip().startswith("AtomData:"))
    forces = []
    for line in lines[atom_line + 1:atom_line + 1 + count]:
        fields = line.split()
        forces.append([float(fields[5]), float(fields[6]), float(fields[7])])
    energy_line = next(index for index, line in enumerate(lines) if line.strip() == "Energy")
    stress_line = next(index for index, line in enumerate(lines) if line.strip().startswith("PlusStress:"))
    return {
        "energy": float(lines[energy_line + 1]),
        "forces": forces,
        "virial": [float(value) for value in lines[stress_line + 1].split()],
    }


def run_reference(packet):
    validate_case(packet)
    with tempfile.TemporaryDirectory(prefix="mtp-reference-") as temp_name:
        directory = Path(temp_name)
        source = directory / "input.cfg"
        output = directory / "output.cfg"
        _write_cfg(source, packet)
        environment = dict(os.environ)
        environment["LD_LIBRARY_PATH"] = str(LIBRARIES)
        completed = subprocess.run(
            [str(REFERENCE), "calculate_efs", str(POTENTIAL), str(source),
             f"--output_filename={output}"],
            text=True, capture_output=True, timeout=40, check=False, env=environment,
        )
        if completed.returncode:
            raise RuntimeError(
                f"MLIP-3 failed ({completed.returncode}): "
                f"{completed.stderr[-1200:]}{completed.stdout[-600:]}"
            )
        return _parse_cfg(output, len(packet["positions"]))


def main():
    for line in sys.stdin:
        try:
            packet = json.loads(line)
            print(json.dumps({"ok": True, "result": run_reference(packet)},
                             separators=(",", ":")), flush=True)
        except Exception as error:
            print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}),
                  flush=True)


if __name__ == "__main__":
    main()
