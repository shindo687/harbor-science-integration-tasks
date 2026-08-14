"""Static isolation and donor-copy checks for the submitted source tree."""

from __future__ import annotations

from pathlib import Path
import hashlib
import os
import re


TOKEN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*)|(?:0[xX][0-9A-Fa-f]+)|"
    r"(?:[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)|"
    r"(?:==|!=|<=|>=|->|\+\+|--|&&|\|\||<<|>>|\+=|-=|\*=|/=)|"
    r"(?:[^\s])"
)
COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
STRINGS = re.compile(r'"(?:\\.|[^"\\])*"', re.S)

FORBIDDEN_CALL = re.compile(
    r"\b(?:system|popen|pclose|fork|vfork|execl|execle|execlp|execv|execve|"
    r"execvp|posix_spawn|dlopen|dlsym)\s*\("
)
FORBIDDEN_STRING_PARTS = (
    "mafft",
    "/opt/reference",
    "/tests/",
    "python",
    "perl",
    "curl",
    "wget",
    "http://",
    "https://",
)


def _without_comments(text):
    return COMMENTS.sub(" ", text)


def _tokens(text, normalized=False):
    text = STRINGS.sub(" STR ", _without_comments(text))
    values = TOKEN.findall(text)
    if not normalized:
        return values
    keywords = {
        "auto", "break", "case", "char", "const", "continue", "default",
        "do", "double", "else", "enum", "extern", "float", "for", "goto",
        "if", "inline", "int", "long", "register", "restrict", "return",
        "short", "signed", "sizeof", "static", "struct", "switch", "typedef",
        "union", "unsigned", "void", "volatile", "while", "_Bool",
    }
    result = []
    for value in values:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) and value not in keywords:
            result.append("ID")
        elif re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+)|(?:[0-9].*)", value):
            result.append("NUM")
        else:
            result.append(value)
    return result


def _window_hashes(tokens, width):
    if len(tokens) < width:
        return set()
    return {
        hashlib.sha256("\x1f".join(tokens[i : i + width]).encode()).digest()
        for i in range(len(tokens) - width + 1)
    }


def _source_texts(root):
    paths = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".c", ".h"}
    )
    return paths, "\n".join(path.read_text(errors="replace") for path in paths)


def check_source_policy(testbed, pristine_root, donor_root):
    testbed = Path(testbed)
    problems = []
    details = {}
    if not testbed.is_dir():
        return ["/testbed is missing"], details

    all_files = []
    for path in testbed.rglob("*"):
        try:
            stat = path.lstat()
        except OSError as exc:
            problems.append(f"cannot stat {path.relative_to(testbed)}: {exc}")
            continue
        rel = path.relative_to(testbed)
        if path.is_symlink():
            problems.append(f"symbolic links are forbidden: {rel}")
        elif path.is_file():
            all_files.append(path)
            if stat.st_mode & 0o6000:
                problems.append(f"set-id file is forbidden: {rel}")
            if path.name != "FastTree":
                head = path.read_bytes()[:4]
                if head == b"\x7fELF":
                    problems.append(f"bundled executable is forbidden: {rel}")
                if head[:2] in {b"PK", b"\x1f\x8b"}:
                    problems.append(f"bundled archive is forbidden: {rel}")

    source_paths, candidate_text = _source_texts(testbed)
    details["source_files"] = [str(path.relative_to(testbed)) for path in source_paths]
    total_source_bytes = sum(path.stat().st_size for path in source_paths)
    details["source_bytes"] = total_source_bytes
    if not (testbed / "FastTree.c").is_file():
        problems.append("FastTree.c is missing")
    if not source_paths:
        problems.append("no C source was submitted")
    if len(source_paths) > 24:
        problems.append("too many C/header files")
    if total_source_bytes > 3_000_000:
        problems.append("submitted C/header source exceeds 3 MB")
    if "--align-small" not in candidate_text:
        problems.append("required --align-small interface is absent from C source")

    code = _without_comments(candidate_text)
    if FORBIDDEN_CALL.search(code):
        problems.append("process execution or dynamic loading call found in C source")
    for literal in STRINGS.findall(code):
        lowered = literal.lower()
        for part in FORBIDDEN_STRING_PARTS:
            if part in lowered:
                problems.append(f"forbidden runtime string in C source: {part}")
                break

    pristine_fasttree = Path(pristine_root) / "FastTree.c"
    candidate_fasttree = testbed / "FastTree.c"
    if pristine_fasttree.is_file() and candidate_fasttree.is_file():
        pristine_hash = hashlib.sha256(pristine_fasttree.read_bytes()).hexdigest()
        candidate_hash = hashlib.sha256(candidate_fasttree.read_bytes()).hexdigest()
        details["pristine_fasttree_sha256"] = pristine_hash
        details["candidate_fasttree_sha256"] = candidate_hash
        if pristine_hash == candidate_hash and len(source_paths) == 1:
            problems.append("host source is unchanged and no integration source was added")

    donor_paths, donor_text = _source_texts(Path(donor_root) / "core")
    details["donor_source_files"] = len(donor_paths)
    exact_donor = _window_hashes(_tokens(donor_text), 72)
    exact_candidate = _window_hashes(_tokens(candidate_text), 72)
    exact_overlap = len(exact_donor & exact_candidate)
    details["donor_exact_72_token_windows"] = exact_overlap
    if exact_overlap:
        problems.append("candidate contains a 72-token exact MAFFT-source fragment")

    normalized_donor = _window_hashes(_tokens(donor_text, normalized=True), 128)
    normalized_candidate = _window_hashes(_tokens(candidate_text, normalized=True), 128)
    normalized_overlap = len(normalized_donor & normalized_candidate)
    details["donor_normalized_128_token_windows"] = normalized_overlap
    if normalized_overlap:
        problems.append("candidate contains a normalized 128-token MAFFT-source fragment")

    details["regular_files"] = len(all_files)
    return sorted(set(problems)), details

