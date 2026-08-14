#!/usr/bin/env python3
"""Verify that aggregate task subtrees equal their locked standalone commits."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
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


def subtree_stats(revision: str) -> tuple[dict[str, int], int]:
    listing = git("ls-tree", "-rl", revision)
    blob_sizes: dict[str, int] = {}
    over_limit = 0
    for line in listing.splitlines():
        metadata, path = line.split("\t", 1)
        fields = metadata.split()
        if fields[1] != "blob":
            continue
        size = int(fields[3])
        blob_sizes[path] = size
        over_limit += size >= 100_000_000
    return blob_sizes, over_limit


def lfs_stats(name: str, blob_sizes: dict[str, int]) -> dict[str, int]:
    prefix = f"tasks/{name}/"
    grep = subprocess.run(
        [
            "git",
            "-C",
            str(ROOT),
            "grep",
            "-Il",
            "^version https://git-lfs.github.com/spec/v1$",
            "HEAD",
            "--",
            f"tasks/{name}",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if grep.returncode not in (0, 1):
        raise RuntimeError(grep.stderr.strip())

    objects: dict[str, int] = {}
    pointer_blob_bytes = 0
    file_count = 0
    for raw_match in grep.stdout.splitlines():
        _revision, full_path = raw_match.split(":", 1)
        if not full_path.startswith(prefix):
            raise RuntimeError(f"unexpected LFS path: {full_path}")
        path = full_path.removeprefix(prefix)
        pointer = git("show", f"HEAD:{full_path}")
        oid_match = re.search(r"^oid sha256:([0-9a-f]{64})$", pointer, re.MULTILINE)
        size_match = re.search(r"^size ([0-9]+)$", pointer, re.MULTILINE)
        if oid_match is None or size_match is None:
            raise RuntimeError(f"malformed LFS pointer: {full_path}")
        oid = oid_match.group(1)
        size = int(size_match.group(1))
        if oid in objects and objects[oid] != size:
            raise RuntimeError(f"conflicting LFS sizes for {oid}")
        objects[oid] = size
        pointer_blob_bytes += blob_sizes[path]
        file_count += 1

    git_blob_bytes = sum(blob_sizes.values())
    lfs_bytes = sum(objects.values())
    return {
        "file_count": len(blob_sizes),
        "git_blob_bytes": git_blob_bytes,
        "lfs_file_count": file_count,
        "lfs_object_count": len(objects),
        "lfs_bytes": lfs_bytes,
        "materialized_bytes": git_blob_bytes - pointer_blob_bytes + lfs_bytes,
    }


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

    if lock.get("schema_version") != 2:
        errors.append("tasks.lock.json must use schema_version 2")
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
            blob_sizes, over_limit = subtree_stats(f"HEAD:tasks/{name}")
            stats = lfs_stats(name, blob_sizes)
        except (RuntimeError, subprocess.CalledProcessError) as exc:
            detail = str(exc)
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                detail = exc.stderr.strip()
            errors.append(f"{name}: cannot inspect committed subtree: {detail}")
            continue
        if actual_tree != entry["source_tree"]:
            errors.append(
                f"{name}: tree mismatch {actual_tree} != {entry['source_tree']}"
            )
        for field, actual in stats.items():
            if actual != entry.get(field):
                errors.append(
                    f"{name}: {field} mismatch {actual} != {entry.get(field)}"
                )
        if over_limit:
            errors.append(f"{name}: {over_limit} files violate GitHub's 100 MB limit")
        print(
            f"OK {name}: tree={actual_tree} files={stats['file_count']} "
            f"materialized_bytes={stats['materialized_bytes']}"
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
