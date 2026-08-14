"""Dependency-free alignment and Newick helpers shared by the verifier."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
import re


DNA = frozenset("ACGTN")
PROTEIN = frozenset("ABCDEFGHIKLMNPQRSTVWXYZ")

_BLOSUM62_ORDER = "ARNDCQEGHILKMFPSTWYV"
_BLOSUM62_ROWS = (
    "4 -1 -2 -2 0 -1 -1 0 -2 -1 -1 -1 -1 -2 -1 1 0 -3 -2 0",
    "-1 5 0 -2 -3 1 0 -2 0 -3 -2 2 -1 -3 -2 -1 -1 -3 -2 -3",
    "-2 0 6 1 -3 0 0 0 1 -3 -3 0 -2 -3 -2 1 0 -4 -2 -3",
    "-2 -2 1 6 -3 0 2 -1 -1 -3 -4 -1 -3 -3 -1 0 -1 -4 -3 -3",
    "0 -3 -3 -3 9 -3 -4 -3 -3 -1 -1 -3 -1 -2 -3 -1 -1 -2 -2 -1",
    "-1 1 0 0 -3 5 2 -2 0 -3 -2 1 0 -3 -1 0 -1 -2 -1 -2",
    "-1 0 0 2 -4 2 5 -2 0 -3 -3 1 -2 -3 -1 0 -1 -3 -2 -2",
    "0 -2 0 -1 -3 -2 -2 6 -2 -4 -4 -2 -3 -3 -2 0 -2 -2 -3 -3",
    "-2 0 1 -1 -3 0 0 -2 8 -3 -3 -1 -2 -1 -2 -1 -2 -2 2 -3",
    "-1 -3 -3 -3 -1 -3 -3 -4 -3 4 2 -3 1 0 -3 -2 -1 -3 -1 3",
    "-1 -2 -3 -4 -1 -2 -3 -4 -3 2 4 -2 2 0 -3 -2 -1 -2 -1 1",
    "-1 2 0 -1 -3 1 1 -2 -1 -3 -2 5 -1 -3 -1 0 -1 -3 -2 -2",
    "-1 -1 -2 -3 -1 0 -2 -3 -2 1 2 -1 5 0 -2 -1 -1 -1 -1 1",
    "-2 -3 -3 -3 -2 -3 -3 -3 -1 0 0 -3 0 6 -4 -2 -2 1 3 -1",
    "-1 -2 -2 -1 -3 -1 -1 -2 -2 -3 -3 -1 -2 -4 7 -1 -1 -4 -3 -2",
    "1 -1 1 0 -1 0 0 0 -1 -2 -2 0 -1 -2 -1 4 1 -3 -2 -2",
    "0 -1 0 -1 -1 -1 -1 -2 -2 -1 -1 -1 -1 -2 -1 1 5 -2 -2 0",
    "-3 -3 -4 -4 -2 -2 -3 -2 -2 -3 -2 -3 -1 1 -4 -3 -2 11 2 -3",
    "-2 -2 -2 -3 -2 -1 -2 -3 2 -1 -1 -2 -1 3 -3 -2 -2 2 7 -1",
    "0 -3 -3 -3 -1 -2 -2 -3 -3 3 1 -2 1 -1 -2 -2 0 -3 -1 4",
)
_BLOSUM62 = {
    (left, right): int(value)
    for left, row in zip(_BLOSUM62_ORDER, _BLOSUM62_ROWS)
    for right, value in zip(_BLOSUM62_ORDER, row.split())
}


def parse_fasta(text: str):
    records = []
    name = None
    chunks = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if name is not None:
                records.append((name, "".join(chunks).upper()))
            header = line[1:].strip()
            if not header:
                raise ValueError("empty FASTA header")
            name = header.split()[0]
            chunks = []
        else:
            if name is None:
                raise ValueError("sequence before first FASTA header")
            chunks.append(line)
    if name is not None:
        records.append((name, "".join(chunks).upper()))
    if not records:
        raise ValueError("empty FASTA")
    names = [name for name, _ in records]
    if len(set(names)) != len(names):
        raise ValueError("duplicate FASTA identifier")
    return records


def format_fasta(records):
    return "".join(f">{name}\n{seq}\n" for name, seq in records)


def alignment_homology(records):
    records = sorted(records)
    if not records:
        return frozenset()
    widths = {len(seq) for _, seq in records}
    if len(widths) != 1:
        raise ValueError("alignment rows have unequal width")
    positions = {name: 0 for name, _ in records}
    pairs = set()
    for column in range(next(iter(widths))):
        residues = []
        for name, seq in records:
            if seq[column] != "-":
                residues.append((name, positions[name]))
                positions[name] += 1
        for i, left in enumerate(residues):
            for right in residues[i + 1 :]:
                pairs.add((left[0], left[1], right[0], right[1]))
    return frozenset(pairs)


def alignment_invariants(input_records, aligned_records, alphabet):
    problems = []
    source = dict(input_records)
    output = dict(aligned_records)
    if len(output) != len(aligned_records):
        problems.append("duplicate output identifier")
    if set(source) != set(output):
        problems.append("output identifier set differs from input")
    widths = {len(seq) for seq in output.values()}
    if len(widths) != 1:
        problems.append("alignment rows have unequal width")
    allowed = DNA if alphabet == "dna" else PROTEIN
    for name in sorted(set(source) & set(output)):
        aligned = output[name].upper()
        if aligned.replace("-", "") != source[name].upper():
            problems.append(f"ungapped sequence changed: {name}")
        illegal = set(aligned) - allowed - {"-"}
        if illegal:
            problems.append(f"illegal symbols for {name}: {sorted(illegal)}")
    if len(widths) == 1 and output:
        width = next(iter(widths))
        for col in range(width):
            if all(seq[col] == "-" for seq in output.values()):
                problems.append(f"all-gap column: {col}")
                break
    return problems


def affine_sp_score(records, alphabet, gap_open, gap_extend):
    """Independent affine sum-of-pairs score for a completed alignment."""
    records = sorted(records)
    widths = {len(seq) for _, seq in records}
    if len(widths) != 1:
        raise ValueError("alignment rows have unequal width")
    total = 0.0
    for i, (_, left) in enumerate(records):
        for _, right in records[i + 1 :]:
            gap_state = 0
            for a, b in zip(left, right):
                if a == "-" and b == "-":
                    gap_state = 0
                elif a == "-" or b == "-":
                    state = 1 if a == "-" else 2
                    total -= gap_extend if state == gap_state else gap_open
                    gap_state = state
                else:
                    gap_state = 0
                    if alphabet == "dna":
                        total += 2 if a == b else -1
                    else:
                        total += _BLOSUM62.get((a, b), -1)
    return total


@dataclass(eq=False)
class Node:
    name: str | None = None
    length: float | None = None
    children: list["Node"] = field(default_factory=list)


class _NewickParser:
    def __init__(self, text):
        self.text = text
        self.i = 0

    def skip(self):
        while self.i < len(self.text) and self.text[self.i].isspace():
            self.i += 1

    def token(self):
        self.skip()
        if self.i < len(self.text) and self.text[self.i] == "'":
            self.i += 1
            out = []
            while self.i < len(self.text):
                char = self.text[self.i]
                self.i += 1
                if char == "'":
                    if self.i < len(self.text) and self.text[self.i] == "'":
                        out.append("'")
                        self.i += 1
                        continue
                    return "".join(out)
                out.append(char)
            raise ValueError("unterminated quoted Newick label")
        start = self.i
        while self.i < len(self.text) and self.text[self.i] not in ":,();" \
                and not self.text[self.i].isspace():
            self.i += 1
        return self.text[start:self.i]

    def subtree(self):
        self.skip()
        children = []
        name = None
        if self.i < len(self.text) and self.text[self.i] == "(":
            self.i += 1
            while True:
                children.append(self.subtree())
                self.skip()
                if self.i >= len(self.text):
                    raise ValueError("unterminated Newick group")
                if self.text[self.i] == ",":
                    self.i += 1
                    continue
                if self.text[self.i] == ")":
                    self.i += 1
                    break
                raise ValueError(f"unexpected Newick character {self.text[self.i]!r}")
            label = self.token()
            name = label or None
        else:
            name = self.token()
            if not name:
                raise ValueError("missing Newick leaf label")
        self.skip()
        length = None
        if self.i < len(self.text) and self.text[self.i] == ":":
            self.i += 1
            raw = self.token()
            try:
                length = float(raw)
            except ValueError as exc:
                raise ValueError(f"invalid Newick branch length {raw!r}") from exc
            if not math.isfinite(length):
                raise ValueError("non-finite Newick branch length")
        return Node(name=name, length=length, children=children)

    def parse(self):
        root = self.subtree()
        self.skip()
        if self.i >= len(self.text) or self.text[self.i] != ";":
            raise ValueError("Newick must end with semicolon")
        self.i += 1
        self.skip()
        if self.i != len(self.text):
            raise ValueError("trailing text after Newick")
        return root


def parse_newick(text):
    return _NewickParser(text).parse()


def normalize_mafft_names(root):
    for node in walk(root):
        if not node.children and node.name is not None:
            node.name = re.sub(r"^[0-9]+_", "", node.name)
    return root


def walk(root):
    yield root
    for child in root.children:
        yield from walk(child)


def leaf_names(root):
    names = [node.name for node in walk(root) if not node.children]
    if any(name is None for name in names) or len(names) != len(set(names)):
        raise ValueError("tree leaves must have unique non-empty names")
    return frozenset(names)


def _leaf_sets(root):
    sets = {}

    def visit(node):
        if not node.children:
            value = frozenset([node.name])
        else:
            value = frozenset().union(*(visit(child) for child in node.children))
        sets[node] = value
        return value

    visit(root)
    return sets


def normalized_splits(root):
    sets = _leaf_sets(root)
    leaves = sets[root]
    result = set()
    for node, side in sets.items():
        if node is root or len(side) <= 1 or len(leaves - side) <= 1:
            continue
        other = leaves - side
        left = tuple(sorted(side))
        right = tuple(sorted(other))
        result.add(min(left, right))
    return frozenset(result)


def tree_distances(root):
    graph = {}
    named = {}

    def visit(node):
        graph.setdefault(node, [])
        if not node.children:
            named[node.name] = node
        for child in node.children:
            length = 0.0 if child.length is None else child.length
            graph[node].append((child, length))
            graph.setdefault(child, []).append((node, length))
            visit(child)

    visit(root)
    result = {}
    for source_name, source in named.items():
        stack = [(source, None, 0.0)]
        while stack:
            node, parent, distance = stack.pop()
            if not node.children and node.name > source_name:
                result[(source_name, node.name)] = distance
            for nxt, length in graph[node]:
                if nxt is not parent:
                    stack.append((nxt, node, distance + length))
    return result


def tree_invariants(root, expected_names, require_ultrametric=False):
    problems = []
    try:
        names = leaf_names(root)
    except ValueError as exc:
        return [str(exc)]
    if names != frozenset(expected_names):
        problems.append("tree leaf set differs from input")
    for node in walk(root):
        if node is root:
            continue
        if node.length is None:
            problems.append("tree edge lacks branch length")
        elif node.length < -1e-8 or not math.isfinite(node.length):
            problems.append("tree has negative or non-finite branch length")
    if require_ultrametric:
        depths = []

        def descend(node, distance):
            if not node.children:
                depths.append(distance)
            for child in node.children:
                descend(child, distance + (child.length or 0.0))

        descend(root, 0.0)
        if depths and max(depths) - min(depths) > 2e-4:
            problems.append("guide tree is not ultrametric")
    return problems


def homology_f1(reference, candidate):
    if not reference and not candidate:
        return 1.0
    return 2.0 * len(reference & candidate) / max(1, len(reference) + len(candidate))


def trees_equivalent(reference, candidate, branch_tolerance=1e-5):
    if leaf_names(reference) != leaf_names(candidate):
        return False, "leaf sets differ"
    if normalized_splits(reference) != normalized_splits(candidate):
        return False, "normalized split sets differ"
    ref_dist = tree_distances(reference)
    got_dist = tree_distances(candidate)
    if set(ref_dist) != set(got_dist):
        return False, "leaf-pair distance keys differ"
    worst = max((abs(ref_dist[key] - got_dist[key]) for key in ref_dist), default=0.0)
    if worst > branch_tolerance:
        return False, f"leaf-pair branch distance error {worst:.8g} exceeds {branch_tolerance}"
    return True, "ok"
