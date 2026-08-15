#!/usr/bin/env python3
"""Unprivileged adapter for the submitted GATK Java source file."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys


CLASSES = os.environ.get("CANDIDATE_CLASSES", "/tmp/algobridge-candidate-classes")
JAVA = os.path.join(os.environ.get("JAVA_HOME", "/opt/java/openjdk"), "bin", "java")


def encode(value):
    return base64.urlsafe_b64encode(value.encode("utf-8")).decode("ascii").rstrip("=")


def decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode("utf-8")


def request_text(packet):
    lines = [f"R\t{packet['reference_start']}\t{encode(packet['reference'])}"]
    for side, tag in (("truth", "T"), ("query", "Q")):
        variants = packet[side]
        if variants is None:
            lines.append(f"{tag}\t{encode('__NULL_LIST__')}\t0\tQQ\tQQ\tQQ")
            continue
        for item in variants:
            lines.append("\t".join((
                tag, encode(item["id"]), str(item["position"]), encode(item["ref"]),
                encode(item["alt"]), encode(item["genotype"]),
            )))
    lines.append("E")
    return "\n".join(lines) + "\n"


def parse_result(stdout):
    lines = stdout.splitlines()
    if not lines:
        raise RuntimeError("candidate harness produced no output")
    if lines[0].startswith("ERROR\t"):
        return {"ok": False, "error": decode(lines[0].split("\t", 1)[1])}
    if lines[0] != "OK":
        raise RuntimeError("candidate harness emitted an invalid header")
    truth, query, summary = [], [], None
    for line in lines[1:]:
        fields = line.split("\t")
        if fields[0] in {"T", "Q"} and len(fields) == 3:
            target = truth if fields[0] == "T" else query
            target.append({"id": decode(fields[1]), "status": fields[2]})
        elif fields[0] == "S" and len(fields) == 8:
            summary = {
                "truth_tp": int(fields[1]), "query_tp": int(fields[2]),
                "fp": int(fields[3]), "fn": int(fields[4]),
                "precision": float(fields[5]), "recall": float(fields[6]),
                "f1": float(fields[7]),
            }
        else:
            raise RuntimeError("candidate harness emitted a malformed row")
    if summary is None:
        raise RuntimeError("candidate harness omitted the summary")
    return {"ok": True, "result": {"truth": truth, "query": query, "summary": summary}}


def main():
    for line in sys.stdin:
        try:
            packet = json.loads(line)
            completed = subprocess.run(
                [JAVA, "-Xms16m", "-Xmx128m", "-cp", CLASSES, "HaplotypeCompareHarness"],
                input=request_text(packet), text=True, capture_output=True,
                timeout=20, check=False,
            )
            if completed.returncode:
                raise RuntimeError(
                    f"Java harness failed ({completed.returncode}): {completed.stderr[-1200:]}"
                )
            print(json.dumps(parse_result(completed.stdout), separators=(",", ":")), flush=True)
        except Exception as error:
            print(json.dumps({"ok": False, "error": f"{type(error).__name__}: {error}"}), flush=True)


if __name__ == "__main__":
    main()
