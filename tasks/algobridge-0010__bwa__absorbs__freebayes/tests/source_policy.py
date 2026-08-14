"""Static donor-isolation and submitted-source checks."""

from __future__ import annotations

from pathlib import Path
import hashlib
import re


TOKEN = re.compile(
    r"(?:[A-Za-z_][A-Za-z0-9_]*)|(?:0[xX][0-9A-Fa-f]+)|"
    r"(?:[0-9]+(?:\.[0-9]*)?(?:[eE][+-]?[0-9]+)?)|"
    r"(?:==|!=|<=|>=|->|\+\+|--|&&|\|\||<<|>>|\+=|-=|\*=|/=)|(?:[^\s])"
)
COMMENTS = re.compile(r"/\*.*?\*/|//[^\n]*", re.S)
STRINGS = re.compile(r'"(?:\\.|[^"\\])*"', re.S)
FORBIDDEN_CALL = re.compile(
    r"\b(?:system|popen|pclose|fork|vfork|execl|execle|execlp|execv|execve|"
    r"execvp|posix_spawn|dlopen|dlsym)\s*\("
)
FORBIDDEN_STRING_PARTS = (
    "freebayes",
    "vcflib",
    "/opt/reference",
    "/tests/",
    "python",
    "perl",
    "curl",
    "wget",
    "http://",
    "https://",
)
SOURCE_SUFFIXES = {".c", ".h", ".cc", ".cpp", ".cxx", ".hpp"}


def _without_comments(text: str) -> str:
    return COMMENTS.sub(" ", text)


def _tokens(text: str, *, normalized: bool = False) -> list[str]:
    values = TOKEN.findall(STRINGS.sub(" STR ", _without_comments(text)))
    if not normalized:
        return values
    keywords = {
        "auto", "break", "case", "char", "const", "continue", "default", "do",
        "double", "else", "enum", "extern", "float", "for", "goto", "if",
        "inline", "int", "long", "register", "restrict", "return", "short",
        "signed", "sizeof", "static", "struct", "switch", "typedef", "union",
        "unsigned", "void", "volatile", "while", "_Bool", "bool", "class",
        "namespace", "public", "private", "protected", "template", "typename",
    }
    result: list[str] = []
    for value in values:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value) and value not in keywords:
            result.append("ID")
        elif re.fullmatch(r"(?:0[xX][0-9A-Fa-f]+)|(?:[0-9].*)", value):
            result.append("NUM")
        else:
            result.append(value)
    return result


def _window_hashes(tokens: list[str], width: int) -> set[bytes]:
    if len(tokens) < width:
        return set()
    return {
        hashlib.sha256("\x1f".join(tokens[index : index + width]).encode()).digest()
        for index in range(len(tokens) - width + 1)
    }


def _source_texts(root: Path, *, donor: bool = False) -> tuple[list[Path], str]:
    search_root = root / "src" if donor and (root / "src").is_dir() else root
    paths = sorted(
        path for path in search_root.rglob("*")
        if path.is_file() and path.suffix.lower() in SOURCE_SUFFIXES
    )
    return paths, "\n".join(path.read_text(errors="replace") for path in paths)


def check_source_policy(testbed: Path, pristine_root: Path, donor_root: Path):
    problems: list[str] = []
    details: dict[str, object] = {}
    if not testbed.is_dir():
        return ["/testbed is missing"], details

    regular_files: list[Path] = []
    for path in testbed.rglob("*"):
        relative = path.relative_to(testbed)
        try:
            stat = path.lstat()
        except OSError as error:
            problems.append(f"cannot stat {relative}: {error}")
            continue
        if path.is_symlink():
            problems.append(f"symbolic links are forbidden: {relative}")
        elif path.is_file():
            regular_files.append(path)
            if stat.st_mode & 0o6000:
                problems.append(f"set-id file is forbidden: {relative}")
            head = path.read_bytes()[:4]
            if head == b"\x7fELF" and path.name != "bwa" and path.suffix != ".o":
                problems.append(f"bundled executable is forbidden: {relative}")
            if head[:2] in {b"PK", b"\x1f\x8b"}:
                problems.append(f"bundled archive is forbidden: {relative}")

    source_paths, candidate_text = _source_texts(testbed)
    source_bytes = sum(path.stat().st_size for path in source_paths)
    details["source_files"] = [str(path.relative_to(testbed)) for path in source_paths]
    details["source_bytes"] = source_bytes
    details["regular_files"] = len(regular_files)
    if not (testbed / "main.c").is_file() or not (testbed / "Makefile").is_file():
        problems.append("required BWA main.c or Makefile is missing")
    if not source_paths:
        problems.append("no C/C++ source was submitted")
    if len(source_paths) > 256:
        problems.append("too many source files")
    if source_bytes > 12_000_000:
        problems.append("submitted source exceeds 12 MB")
    if "snv-call" not in candidate_text:
        problems.append("required snv-call interface is absent from source")

    changed_paths = []
    for path in source_paths:
        pristine_path = pristine_root / path.relative_to(testbed)
        if not pristine_path.is_file() or pristine_path.read_bytes() != path.read_bytes():
            changed_paths.append(path)
    changed_text = "\n".join(path.read_text(errors="replace") for path in changed_paths)
    details["changed_source_files"] = [str(path.relative_to(testbed)) for path in changed_paths]

    code = _without_comments(changed_text)
    if FORBIDDEN_CALL.search(code):
        problems.append("process execution or dynamic loading call found in source")
    for literal in STRINGS.findall(code):
        lowered = literal.lower()
        for part in FORBIDDEN_STRING_PARTS:
            if part in lowered:
                problems.append(f"forbidden runtime string in source: {part}")
                break

    pristine_main = pristine_root / "main.c"
    if pristine_main.is_file() and (testbed / "main.c").is_file():
        pristine_hash = hashlib.sha256(pristine_main.read_bytes()).hexdigest()
        candidate_hash = hashlib.sha256((testbed / "main.c").read_bytes()).hexdigest()
        details["pristine_main_sha256"] = pristine_hash
        details["candidate_main_sha256"] = candidate_hash
        if pristine_hash == candidate_hash:
            problems.append("BWA dispatcher is unchanged; snv-call is not integrated")

    donor_paths, donor_text = _source_texts(donor_root, donor=True)
    details["donor_source_files"] = len(donor_paths)
    exact_overlap = len(
        _window_hashes(_tokens(donor_text), 72)
        & _window_hashes(_tokens(changed_text), 72)
    )
    normalized_overlap = len(
        _window_hashes(_tokens(donor_text, normalized=True), 128)
        & _window_hashes(_tokens(changed_text, normalized=True), 128)
    )
    details["donor_exact_72_token_windows"] = exact_overlap
    details["donor_normalized_128_token_windows"] = normalized_overlap
    if exact_overlap:
        problems.append("candidate contains a 72-token exact FreeBayes-source fragment")
    if normalized_overlap:
        problems.append("candidate contains a normalized 128-token FreeBayes-source fragment")
    return sorted(set(problems)), details
