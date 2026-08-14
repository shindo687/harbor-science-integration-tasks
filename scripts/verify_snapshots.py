#!/usr/bin/env python3
"""Verify that aggregate task subtrees equal their locked standalone commits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def git(*args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(ROOT), *args],
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def subtree_stats(revision: str) -> tuple[int, int, int]:
    listing = git("ls-tree", "-rl", revision)
    count = 0
    total = 0
    over_limit = 0
    for line in listing.splitlines():
        metadata, _path = line.split("\t", 1)
        fields = metadata.split()
        if fields[1] != "blob":
            continue
        size = int(fields[3])
        count += 1
        total += size
        over_limit += size >= 100_000_000
    return count, total, over_limit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()

    source_entries = load(ROOT / "task-sources.json")["tasks"]
    lock = load(ROOT / "tasks.lock.json")
    locked_entries = lock["tasks"]
    sources = {entry["name"]: entry for entry in source_entries}
    locked = {entry["name"]: entry for entry in locked_entries}
    errors: list[str] = []

    if len(sources) != len(source_entries):
        errors.append("task-sources.json contains duplicate names")
    if len(locked) != len(locked_entries):
        errors.append("tasks.lock.json contains duplicate names")
    if not args.allow_partial and set(locked) != set(sources):
        missing = sorted(set(sources) - set(locked))
        extra = sorted(set(locked) - set(sources))
        errors.append(f"lock/source mismatch; missing={missing}, extra={extra}")
    if lock["task_count"] != len(locked_entries):
        errors.append("task_count does not match lock entries")
    if not args.allow_partial and not lock.get("complete"):
        errors.append("lock is not marked complete")

    directory_names = {
        path.name for path in (ROOT / "tasks").iterdir() if path.is_dir() and not path.name.startswith(".")
    }
    if directory_names != set(locked):
        errors.append(
            "task directories do not match lock entries; "
            f"missing={sorted(set(locked) - directory_names)}, "
            f"extra={sorted(directory_names - set(locked))}"
        )

    for name in sorted(locked):
        entry = locked[name]
        source = sources.get(name)
        if source is None:
            errors.append(f"{name}: no source record")
            continue
        for field in ("origin", "commit", "suite"):
            if entry.get(field) != source.get(field):
                errors.append(f"{name}: {field} differs from task-sources.json")
        try:
            actual_tree = git("rev-parse", f"HEAD:tasks/{name}")
            file_count, total_bytes, over_limit = subtree_stats(f"HEAD:tasks/{name}")
        except subprocess.CalledProcessError as exc:
            errors.append(f"{name}: cannot inspect committed subtree: {exc.stderr.strip()}")
            continue
        if actual_tree != entry["source_tree"]:
            errors.append(
                f"{name}: tree mismatch {actual_tree} != {entry['source_tree']}"
            )
        if file_count != entry["file_count"]:
            errors.append(f"{name}: file count mismatch {file_count} != {entry['file_count']}")
        if total_bytes != entry["bytes"]:
            errors.append(f"{name}: byte count mismatch {total_bytes} != {entry['bytes']}")
        if over_limit:
            errors.append(f"{name}: {over_limit} files violate GitHub's 100 MB limit")
        print(
            f"OK {name}: tree={actual_tree} files={file_count} bytes={total_bytes}"
        )

    if errors:
        print("\nFAILED", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"\nPASS: {len(locked)}/{len(sources)} task snapshots verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
