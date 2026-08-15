#!/usr/bin/env python3
"""Deterministic bounded A3M fixtures for ALGOBRIDGE-0008."""

from __future__ import annotations

import copy
import random
import re


ALPHABET = "ARNDCQEGHILKMFPSTWYV"
NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def validate_case(packet: dict) -> None:
    required = {"name", "a3m", "reweight_threshold", "l2_factor", "iterations", "seed"}
    if set(packet) != required:
        raise ValueError("case packet fields differ from the locked schema")
    if not NAME_RE.fullmatch(packet["name"]):
        raise ValueError("invalid case name")
    if not isinstance(packet["a3m"], str) or not packet["a3m"].endswith("\n"):
        raise ValueError("invalid A3M payload")
    if not 0.0 < float(packet["reweight_threshold"]) <= 1.0:
        raise ValueError("invalid reweight threshold")
    if not 0.0 < float(packet["l2_factor"]) <= 10.0:
        raise ValueError("invalid L2 factor")
    if not 1 <= int(packet["iterations"]) <= 250:
        raise ValueError("invalid iteration count")
    if int(packet["seed"]) < 0:
        raise ValueError("invalid seed")


def _alignment(
    name: str,
    length: int,
    count: int,
    seed: int,
    *,
    threshold: float = 0.8,
    l2: float = 0.2,
    iterations: int = 16,
    coupled: tuple[tuple[int, int], ...] = (),
    gap_columns: tuple[int, ...] = (),
    duplicate_period: int = 0,
    insertions: bool = False,
) -> dict:
    rng = random.Random(seed)
    rows: list[str] = []
    for sequence_index in range(count):
        row = [rng.choice(ALPHABET) for _ in range(length)]
        for pair_index, (left, right) in enumerate(coupled):
            latent = (sequence_index * (pair_index + 3) + rng.randrange(7)) % 8
            row[left] = ALPHABET[latent]
            row[right] = ALPHABET[(latent * 3 + pair_index) % 20]
            if sequence_index % 11 == 7:
                row[right] = rng.choice(ALPHABET)
        for column in gap_columns:
            if (sequence_index + column) % 4 != 0:
                row[column] = "-"
        if duplicate_period and sequence_index and sequence_index % duplicate_period == 0:
            row = list(rows[sequence_index - 1].replace("ac", "").replace(".", ""))
        rendered = "".join(row)
        if insertions and sequence_index % 3 == 1:
            pivot = 1 + (sequence_index * 5) % (length - 1)
            rendered = rendered[:pivot] + "ac" + rendered[pivot:]
        elif insertions and sequence_index % 5 == 2:
            pivot = 1 + (sequence_index * 7) % (length - 1)
            rendered = rendered[:pivot] + "." + rendered[pivot:]
        rows.append(rendered)

    lines: list[str] = []
    for index, row in enumerate(rows):
        lines.extend((f">{name}_seq_{index:03d} synthetic", row))
    packet = {
        "name": name,
        "a3m": "\n".join(lines) + "\n",
        "reweight_threshold": threshold,
        "l2_factor": l2,
        "iterations": iterations,
        "seed": seed % 101,
    }
    validate_case(packet)
    return packet


PUBLIC_CASES = [
    _alignment("short_coupled", 8, 12, 101, coupled=((0, 6), (2, 7)), iterations=14),
    _alignment(
        "duplicate_families", 12, 20, 202, coupled=((0, 9), (3, 11)),
        duplicate_period=3, threshold=0.75, l2=0.15, iterations=18,
    ),
    _alignment(
        "gap_heavy", 14, 24, 303, coupled=((1, 10), (4, 12)),
        gap_columns=(2, 7, 11), threshold=0.7, l2=0.25, iterations=16,
    ),
    _alignment(
        "uniform_weights", 15, 18, 404, coupled=((0, 12), (5, 14)),
        threshold=1.0, l2=0.3, iterations=15,
    ),
    _alignment(
        "a3m_insertions", 16, 22, 505, coupled=((1, 13), (6, 15)),
        insertions=True, threshold=0.8, l2=0.2, iterations=17,
    ),
]


def hidden_cases() -> list[dict]:
    return [
        _alignment("minimum_length", 6, 8, 611, coupled=((0, 5),), iterations=10),
        _alignment("two_latent_pairs", 9, 15, 622, coupled=((0, 7), (2, 8)), l2=0.1, iterations=19),
        _alignment("weight_boundary", 10, 16, 633, coupled=((1, 8),), threshold=0.6, iterations=13),
        _alignment("duplicate_pairs", 12, 28, 644, coupled=((0, 10),), duplicate_period=2, iterations=20),
        _alignment("terminal_gaps", 14, 25, 655, coupled=((2, 11),), gap_columns=(0, 13), iterations=14),
        _alignment("three_couplings", 16, 30, 666, coupled=((0, 9), (3, 13), (6, 15)), iterations=20),
        _alignment("mixed_insertions", 18, 32, 677, coupled=((1, 14), (7, 17)), insertions=True, iterations=12),
        _alignment("low_reweight", 20, 36, 688, coupled=((0, 16), (5, 19)), threshold=0.5, iterations=16),
        _alignment("strong_regularization", 22, 34, 699, coupled=((2, 18), (8, 21)), l2=0.45, iterations=15),
        _alignment("sparse_gaps", 24, 40, 710, coupled=((1, 20), (9, 23)), gap_columns=(4, 15), iterations=14),
        _alignment("four_couplings", 26, 42, 721, coupled=((0, 19), (3, 22), (7, 24), (11, 25)), iterations=18),
        _alignment("large_duplicates", 28, 48, 732, coupled=((2, 23), (10, 27)), duplicate_period=4, iterations=13),
        _alignment("long_gap_heavy", 30, 52, 743, coupled=((1, 25), (12, 29)), gap_columns=(5, 17, 26), iterations=12),
        _alignment("largest_fixture", 32, 64, 754, coupled=((0, 27), (6, 30), (14, 31)), l2=0.18, iterations=12),
        _alignment("seed_contract", 17, 27, 765, coupled=((2, 14), (8, 16)), insertions=True, l2=0.35, iterations=17),
    ]


def permuted(packet: dict) -> dict:
    lines = packet["a3m"].strip().splitlines()
    records: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line.startswith(">"):
            if current:
                records.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        records.append(current)
    reordered = copy.deepcopy(packet)
    reordered["name"] += "_permuted"
    reordered["a3m"] = "\n".join(line for record in reversed(records) for line in record) + "\n"
    return reordered
