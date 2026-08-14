#!/usr/bin/env python3
"""Import exact standalone-repository commits into tasks/.

The imported directory is produced by `git archive`, so it contains every
tracked file and preserves Git file modes while excluding standalone `.git`
metadata and untracked local artifacts.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "task-sources.json"
LOCK_PATH = ROOT / "tasks.lock.json"
TASKS_DIR = ROOT / "tasks"
NAME_RE = re.compile(r"(?:algobridge|structharbor)-\d{4}__[a-z0-9_-]+\Z")


def run(*args: str, cwd: Path | None = None, capture: bool = True) -> str:
    result = subprocess.run(
        args,
        cwd=cwd,
        check=True,
        text=True,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def git_object_exists(repo: Path, commit: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "cat-file", "-e", f"{commit}^{{commit}}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def resolve_source(entry: dict, source_root: Path | None, fetch_missing: bool) -> Path:
    name = entry["name"]
    if source_root is not None:
        candidate = source_root / name
        if (candidate / ".git").exists():
            return candidate

    if not fetch_missing:
        raise RuntimeError(
            f"missing local repository {name}; pass --fetch-missing or a valid --source-root"
        )

    cache = ROOT / ".sync-cache" / name
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not (cache / ".git").exists():
        run(
            "git",
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            entry["origin"],
            str(cache),
            capture=False,
        )
    if not git_object_exists(cache, entry["commit"]):
        run(
            "git",
            "-C",
            str(cache),
            "fetch",
            "--depth=1",
            "origin",
            entry["commit"],
            capture=False,
        )
    return cache


def tree_stats(source: Path, commit: str) -> tuple[str, int, int]:
    tree = run("git", "-C", str(source), "rev-parse", f"{commit}^{{tree}}")
    listing = run("git", "-C", str(source), "ls-tree", "-rl", commit)
    count = 0
    total_bytes = 0
    for line in listing.splitlines():
        metadata, _path = line.split("\t", 1)
        fields = metadata.split()
        if fields[1] == "blob":
            count += 1
            total_bytes += int(fields[3])
    return tree, count, total_bytes


def safe_replace_from_archive(source: Path, commit: str, name: str) -> None:
    if not NAME_RE.fullmatch(name):
        raise RuntimeError(f"unsafe task name: {name!r}")
    TASKS_DIR.mkdir(parents=True, exist_ok=True)
    destination = TASKS_DIR / name
    with tempfile.TemporaryDirectory(prefix=f".{name}.", dir=TASKS_DIR) as raw_temp:
        temp = Path(raw_temp)
        archive = subprocess.Popen(
            ["git", "-C", str(source), "archive", "--format=tar", commit],
            stdout=subprocess.PIPE,
        )
        assert archive.stdout is not None
        extract = subprocess.run(
            ["tar", "-xf", "-", "-C", str(temp)],
            stdin=archive.stdout,
        )
        archive.stdout.close()
        archive_status = archive.wait()
        if archive_status != 0 or extract.returncode != 0:
            raise RuntimeError(f"archive extraction failed for {name}")
        if destination.exists():
            shutil.rmtree(destination)
        os.replace(temp, destination)


def write_lock(entries: list[dict], expected_count: int) -> None:
    entries.sort(key=lambda item: item["name"])
    payload = {
        "schema_version": 1,
        "complete": len(entries) == expected_count,
        "task_count": len(entries),
        "tasks": entries,
    }
    temporary = LOCK_PATH.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, LOCK_PATH)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--task", action="append", default=[])
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--fetch-missing", action="store_true")
    args = parser.parse_args()

    sources = load_json(SOURCES_PATH)["tasks"]
    by_name = {entry["name"]: entry for entry in sources}
    if len(by_name) != len(sources):
        raise RuntimeError("duplicate task name in task-sources.json")
    if args.all == bool(args.task):
        parser.error("choose exactly one of --all or one/more --task")
    selected = sorted(by_name) if args.all else args.task
    unknown = sorted(set(selected) - set(by_name))
    if unknown:
        parser.error(f"unknown task(s): {', '.join(unknown)}")

    existing_payload = load_json(LOCK_PATH)
    locked = {entry["name"]: entry for entry in existing_payload["tasks"]}
    source_root = args.source_root.resolve() if args.source_root else None

    for name in selected:
        entry = by_name[name]
        source = resolve_source(entry, source_root, args.fetch_missing)
        if not git_object_exists(source, entry["commit"]):
            raise RuntimeError(f"{source} does not contain locked commit {entry['commit']}")
        tree, file_count, total_bytes = tree_stats(source, entry["commit"])
        safe_replace_from_archive(source, entry["commit"], name)
        locked[name] = {
            **entry,
            "source_tree": tree,
            "file_count": file_count,
            "bytes": total_bytes,
        }
        print(f"synced {name} {entry['commit'][:12]} tree={tree} files={file_count}")

    write_lock(list(locked.values()), len(sources))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
