#!/usr/bin/env python3
"""Generate TASKS.md from the committed provenance lock."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tasks.lock.json"
OUTPUT = ROOT / "TASKS.md"


def main() -> None:
    payload = json.loads(LOCK.read_text(encoding="utf-8"))
    entries = sorted(payload["tasks"], key=lambda entry: entry["name"])
    lines = [
        "# Task index",
        "",
        f"This index contains **{len(entries)}** byte-exact standalone-repository snapshots.",
        "",
        "| Suite | Task snapshot | Standalone repository | Commit | Files | Size |",
        "|---|---|---|---|---:|---:|",
    ]
    for entry in entries:
        name = entry["name"]
        origin = entry["origin"].removesuffix(".git")
        size_mib = entry["bytes"] / 1024 / 1024
        lines.append(
            f"| {entry['suite']} | [{name}](tasks/{name}/) | "
            f"[source]({origin}) | `{entry['commit'][:12]}` | "
            f"{entry['file_count']} | {size_mib:.1f} MiB |"
        )
    lines.extend(
        [
            "",
            "The full source commit and Git tree for every row are recorded in "
            "[`tasks.lock.json`](tasks.lock.json).",
            "",
        ]
    )
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
