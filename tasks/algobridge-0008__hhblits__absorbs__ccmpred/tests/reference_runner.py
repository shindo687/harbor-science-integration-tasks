#!/usr/bin/env python3
"""Root-only locked CCMpred CPU runner."""

from __future__ import annotations

import math
from pathlib import Path
import re
import subprocess
import tempfile


REFERENCE = Path("/opt/reference-ccmpred/ccmpred")
AA = set("ARNDCQEGHILKMFPSTWYV-")


def psicov_rows(a3m: str) -> list[str]:
    rows: list[str] = []
    current: list[str] | None = None
    for line in a3m.splitlines():
        if line.startswith(">"):
            if current is not None:
                rows.append("".join(current))
            current = []
            continue
        if current is None:
            if line.strip():
                raise ValueError("sequence data before first A3M header")
            continue
        for residue in line.strip():
            if residue.islower() or residue == ".":
                continue
            if residue not in AA:
                raise ValueError(f"unsupported A3M residue {residue!r}")
            current.append(residue)
    if current is not None:
        rows.append("".join(current))
    if len(rows) < 2 or len({len(row) for row in rows}) != 1:
        raise ValueError("invalid A3M match-state alignment")
    return rows


def sequence_weights(rows: list[str], threshold: float) -> list[float]:
    if threshold == 1.0:
        return [1.0] * len(rows)
    length = len(rows[0])
    required = math.ceil(threshold * length)
    neighbors = [0] * len(rows)
    for first in range(len(rows)):
        for second in range(first, len(rows)):
            matches = sum(a == b for a, b in zip(rows[first], rows[second]))
            if matches > required:
                neighbors[first] += 1
                neighbors[second] += 1
    return [1.0 / (value - 1) for value in neighbors]


def apc(raw: list[list[float]]) -> list[list[float]]:
    length = len(raw)
    means = [sum(raw[row][column] for row in range(length)) / length for column in range(length)]
    grand = sum(map(sum, raw)) / (length * length)
    if not grand > 0.0:
        raise RuntimeError("oracle produced an all-zero score matrix")
    corrected = [
        [raw[row][column] - means[row] * means[column] / grand for column in range(length)]
        for row in range(length)
    ]
    shift = min(corrected[row][column] for row in range(length) for column in range(row + 1, length))
    for row in range(length):
        for column in range(length):
            corrected[row][column] = 0.0 if row == column else corrected[row][column] - shift
    return corrected


def contacts(matrix: list[list[float]]) -> list[dict]:
    length = len(matrix)
    ranked = [
        (matrix[first][second], first + 1, second + 1)
        for first in range(length)
        for second in range(first + 5, length)
    ]
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return [{"i": first, "j": second, "score": score} for score, first, second in ranked[:length]]


def run_reference(packet: dict) -> dict:
    rows = psicov_rows(packet["a3m"])
    with tempfile.TemporaryDirectory(prefix="ccmpred-reference-") as raw_temp:
        root = Path(raw_temp)
        alignment = root / "input.aln"
        matrix_path = root / "raw.mat"
        alignment.write_text("\n".join(rows) + "\n", encoding="ascii")
        command = [
            str(REFERENCE),
            "-n", str(packet["iterations"]),
            "-e", "0.01",
            "-k", "5",
            "-w", format(float(packet["reweight_threshold"]), ".17g"),
            "-l", format(float(packet["l2_factor"]), ".17g"),
            "-A",
            str(alignment),
            str(matrix_path),
        ]
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, timeout=300, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"CCMpred failed ({completed.returncode}): {completed.stdout[-2000:]}")
        raw = [
            [float(value) for value in line.split()]
            for line in matrix_path.read_text(encoding="ascii").splitlines()
            if line.strip() and not line.startswith("#")
        ]
    length = len(rows[0])
    if len(raw) != length or any(len(row) != length for row in raw):
        raise RuntimeError("CCMpred emitted a malformed score matrix")
    objective_matches = re.findall(r"^Final fx = ([0-9.eE+-]+)$", completed.stdout, re.MULTILINE)
    if len(objective_matches) != 1:
        raise RuntimeError("cannot parse CCMpred final objective")
    progress = re.findall(r"^(\d+)\s+\d+\s+", completed.stdout, re.MULTILINE)
    corrected = apc(raw)
    return {
        "schema_version": 1,
        "length": length,
        "sequence_count": len(rows),
        "effective_sequences": sum(sequence_weights(rows, float(packet["reweight_threshold"]))),
        "parameters": {
            "reweight_threshold": float(packet["reweight_threshold"]),
            "l2_factor": float(packet["l2_factor"]),
            "iterations": int(packet["iterations"]),
            "seed": int(packet["seed"]),
        },
        "diagnostics": {
            "objective": float(objective_matches[0]),
            "iterations_completed": int(progress[-1]) if progress else 0,
            "status": "locked_ccmpred_cpu",
        },
        "raw_score": raw,
        "apc_score": corrected,
        "top_contacts": contacts(corrected),
    }
