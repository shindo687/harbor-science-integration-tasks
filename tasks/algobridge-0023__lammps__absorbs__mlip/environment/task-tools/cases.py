#!/usr/bin/env python3
"""Disclosed and hidden bounded single-element MTP configurations."""

from __future__ import annotations

import math
import random


def case(name, positions, box=14.0):
    return {
        "name": name,
        "box": [float(box), float(box), float(box)],
        "positions": [[float(value) for value in position] for position in positions],
    }


PUBLIC_CASES = [
    case("public_axis_dimer", [[5.0, 5.0, 5.0], [6.7, 5.0, 5.0]]),
    case("public_oblique_triangle", [
        [4.2, 4.4, 4.7], [6.05, 4.65, 4.85], [4.75, 6.35, 5.1],
    ]),
    case("public_asymmetric_tetrahedron", [
        [4.0, 4.0, 4.0], [5.9, 4.1, 4.2], [4.3, 6.1, 4.4], [4.2, 4.5, 6.3],
    ]),
    case("public_bent_chain", [
        [2.5, 5.0, 5.0], [4.05, 5.1, 5.0], [5.6, 5.0, 5.25],
        [7.15, 5.25, 5.05], [8.7, 5.05, 5.35], [10.25, 5.2, 5.1],
    ], 15.0),
    case("public_two_clusters", [
        [2.4, 2.5, 2.6], [4.1, 2.7, 2.8], [2.8, 4.3, 2.9],
        [10.0, 9.9, 10.1], [11.7, 10.2, 10.0], [10.4, 11.7, 10.3],
    ], 16.0),
]


def _random_cluster(name, seed, count, radius, box):
    rng = random.Random(seed)
    center = box / 2.0
    points = []
    attempts = 0
    while len(points) < count and attempts < 100000:
        attempts += 1
        candidate = [center + rng.uniform(-radius, radius) for _ in range(3)]
        if all(math.dist(candidate, point) >= 1.34 for point in points):
            points.append(candidate)
    if len(points) != count:
        raise RuntimeError("deterministic point generator could not satisfy separation")
    return case(name, points, box)


def hidden_cases():
    cases = [
        case("hidden_single_atom", [[7.0, 7.0, 7.0]]),
        case("hidden_near_inner_bound", [[5.0, 5.0, 5.0], [6.279, 5.02, 5.01]]),
        case("hidden_near_cutoff_inside", [[4.0, 4.0, 4.0], [8.998, 4.0, 4.0]], 16.0),
        case("hidden_cutoff_outside", [[4.0, 4.0, 4.0], [9.002, 4.0, 4.0]], 16.0),
        case("hidden_planar_hexagon", [
            [7.0 + 2.0 * math.cos(index * math.pi / 3.0),
             7.0 + 2.0 * math.sin(index * math.pi / 3.0), 7.0]
            for index in range(6)
        ]),
    ]
    specifications = [
        (101, 4, 2.2, 14.0), (202, 5, 2.4, 14.0), (303, 7, 2.6, 15.0),
        (404, 8, 2.8, 16.0), (505, 9, 3.0, 16.0), (606, 10, 3.2, 17.0),
        (707, 12, 3.4, 18.0), (808, 14, 3.7, 19.0), (909, 16, 4.0, 20.0),
        (1001, 18, 4.2, 21.0),
    ]
    for index, (seed, count, radius, box) in enumerate(specifications, 1):
        cases.append(_random_cluster(
            f"hidden_random_cluster_{index:02d}", seed, count, radius, box,
        ))
    return cases


def validate_case(packet):
    if set(packet) != {"name", "box", "positions"}:
        raise ValueError("invalid case schema")
    box = packet["box"]
    positions = packet["positions"]
    if not isinstance(packet["name"], str) or not packet["name"]:
        raise ValueError("case name must be nonempty")
    if not isinstance(box, list) or len(box) != 3 or any(
            not isinstance(value, (int, float)) or not math.isfinite(value) or value < 11.0
            for value in box):
        raise ValueError("box must contain three finite lengths of at least 11")
    if not isinstance(positions, list) or not 1 <= len(positions) <= 20:
        raise ValueError("one to twenty positions are required")
    for point in positions:
        if not isinstance(point, list) or len(point) != 3:
            raise ValueError("each position must have three coordinates")
        for axis, value in enumerate(point):
            if (not isinstance(value, (int, float)) or not math.isfinite(value)
                    or value < 0.0 or value >= box[axis]):
                raise ValueError("position is outside the periodic box")
    for left in range(len(positions)):
        for right in range(left):
            displacement = []
            for axis in range(3):
                value = abs(positions[left][axis] - positions[right][axis])
                displacement.append(min(value, box[axis] - value))
            if math.sqrt(sum(value * value for value in displacement)) < 1.2785:
                raise ValueError("positions are below the potential inner distance")

