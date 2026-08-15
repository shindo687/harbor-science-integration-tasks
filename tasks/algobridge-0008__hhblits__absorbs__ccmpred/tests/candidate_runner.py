#!/usr/bin/env python3
"""Unprivileged runner for the submitted native HH-suite command."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


BINARY = Path(os.environ.get("HHCONTACTS_BINARY", "/testbed/hhcontacts"))
CANDIDATE_ROOT = Path(os.environ.get("HHCONTACTS_ROOT", "/testbed"))
UID = 10001
GID = 10001


def _drop_privileges() -> None:
    if os.geteuid() == 0:
        os.setgroups([])
        os.setgid(GID)
        os.setuid(UID)


def _invoke(a3m: str, arguments: list[str], *, expect_success: bool) -> tuple[int, str, dict | None]:
    with tempfile.TemporaryDirectory(prefix="hhcontacts-candidate-") as raw_temp:
        root = Path(raw_temp)
        root.chmod(0o777)
        alignment = root / "input.a3m"
        output = root / "output.json"
        alignment.write_text(a3m, encoding="ascii")
        alignment.chmod(0o644)
        command = [str(BINARY), "--input", str(alignment), "--output", str(output), *arguments]
        completed = subprocess.run(
            command,
            cwd=str(CANDIDATE_ROOT),
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C"},
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=300,
            check=False,
            preexec_fn=_drop_privileges,
        )
        if not expect_success:
            return completed.returncode, completed.stdout, None
        if completed.returncode != 0:
            raise RuntimeError(f"candidate failed ({completed.returncode}): {completed.stdout[-2000:]}")
        if not output.is_file():
            raise RuntimeError("candidate did not create its JSON output")
        try:
            payload = json.loads(output.read_text(encoding="utf-8"))
        except Exception as error:
            raise RuntimeError(f"candidate output is not valid JSON: {error}") from error
        return completed.returncode, completed.stdout, payload


def _validate(payload: dict) -> None:
    required = {
        "schema_version", "length", "sequence_count", "effective_sequences",
        "parameters", "diagnostics", "raw_score", "apc_score", "top_contacts",
    }
    if set(payload) != required or payload["schema_version"] != 1:
        raise RuntimeError("candidate output schema mismatch")
    length = payload["length"]
    if not isinstance(length, int) or not 2 <= length <= 80:
        raise RuntimeError("candidate output length is invalid")
    for key in ("raw_score", "apc_score"):
        matrix = payload[key]
        if len(matrix) != length or any(len(row) != length for row in matrix):
            raise RuntimeError(f"candidate {key} shape mismatch")
        if any(not math.isfinite(float(value)) for row in matrix for value in row):
            raise RuntimeError(f"candidate {key} contains a non-finite value")
    objective = payload.get("diagnostics", {}).get("objective")
    if not isinstance(objective, (int, float)) or not math.isfinite(objective):
        raise RuntimeError("candidate objective is invalid")
    if not isinstance(payload["top_contacts"], list):
        raise RuntimeError("candidate top-contact list is invalid")


def run_candidate(packet: dict) -> dict:
    arguments = [
        "--reweight-threshold", format(float(packet["reweight_threshold"]), ".17g"),
        "--l2", format(float(packet["l2_factor"]), ".17g"),
        "--iterations", str(int(packet["iterations"])),
        "--seed", str(int(packet["seed"])),
    ]
    _, _, payload = _invoke(packet["a3m"], arguments, expect_success=True)
    assert payload is not None
    _validate(payload)
    return payload


def run_invalid(packet: dict, mode: str) -> bool:
    a3m = packet["a3m"]
    arguments = [
        "--reweight-threshold", str(packet["reweight_threshold"]),
        "--l2", str(packet["l2_factor"]),
        "--iterations", str(packet["iterations"]),
        "--seed", str(packet["seed"]),
    ]
    if mode == "threshold":
        arguments[1] = "1.1"
    elif mode == "l2":
        arguments[3] = "0"
    elif mode == "iterations":
        arguments[5] = "0"
    elif mode == "seed":
        arguments[7] = "-1"
    elif mode == "unequal":
        a3m = ">a\nARND\n>b\nARN\n"
    elif mode == "residue":
        a3m = ">a\nARND\n>b\nARXD\n"
    elif mode == "duplicate":
        a3m = ">same\nARND\n>same\nARND\n"
    elif mode == "too_long":
        row = "A" * 81
        a3m = f">a\n{row}\n>b\n{row}\n"
    else:
        raise ValueError(mode)
    code, _, _ = _invoke(a3m, arguments, expect_success=False)
    return code != 0
