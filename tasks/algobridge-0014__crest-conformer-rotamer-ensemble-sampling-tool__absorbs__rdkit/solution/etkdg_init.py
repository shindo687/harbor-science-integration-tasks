"""Clean-room bounded distance-geometry conformer initialization for CREST."""

from __future__ import annotations

import math


_SCHEMA = "algobridge-crest-etkdg-bounded-v1"


def _number(value):
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError("expected a finite number")
    return float(value)


def _index(value, size):
    if (not isinstance(value, int) or isinstance(value, bool)
            or not 0 <= value < size):
        raise ValueError("atom index out of range")
    return value


def _sub(first, second):
    return [first[i] - second[i] for i in range(3)]


def _dot(first, second):
    return sum(first[i] * second[i] for i in range(3))


def _cross(first, second):
    return [first[1]*second[2] - first[2]*second[1],
            first[2]*second[0] - first[0]*second[2],
            first[0]*second[1] - first[1]*second[0]]


def _norm(value):
    return math.sqrt(max(0.0, _dot(value, value)))


def _distance(first, second):
    return _norm(_sub(first, second))


def _volume(coords, center, neighbors):
    origin = coords[center]
    first, second, third = [_sub(coords[i], origin) for i in neighbors]
    return _dot(first, _cross(second, third))


def _smooth(lower, upper):
    size = len(lower)
    for k in range(size):
        for i in range(size):
            if i == k:
                continue
            for j in range(i + 1, size):
                if j == k:
                    continue
                new_upper = min(upper[i][j], upper[i][k] + upper[k][j])
                new_lower = max(lower[i][j],
                                lower[i][k] - upper[k][j],
                                lower[k][j] - upper[i][k])
                if new_lower > new_upper + 1e-10:
                    raise ValueError("inconsistent distance bounds")
                upper[i][j] = upper[j][i] = new_upper
                lower[i][j] = lower[j][i] = new_lower


class _Random:
    def __init__(self, seed):
        self.state = (int(seed) & 0xFFFFFFFF) or 1

    def uniform(self):
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state / 4294967296.0


def _eigen_symmetric(matrix, sweeps=160):
    size = len(matrix)
    values = [row[:] for row in matrix]
    vectors = [[1.0 if i == j else 0.0 for j in range(size)] for i in range(size)]
    for _ in range(sweeps * max(1, size)):
        largest, p, q = 0.0, 0, 0
        for i in range(size):
            for j in range(i + 1, size):
                if abs(values[i][j]) > largest:
                    largest, p, q = abs(values[i][j]), i, j
        if largest < 1e-12:
            break
        angle = 0.5 * math.atan2(2.0 * values[p][q], values[q][q] - values[p][p])
        cosine, sine = math.cos(angle), math.sin(angle)
        app, aqq, apq = values[p][p], values[q][q], values[p][q]
        for k in range(size):
            if k in (p, q):
                continue
            akp, akq = values[k][p], values[k][q]
            values[k][p] = values[p][k] = cosine*akp - sine*akq
            values[k][q] = values[q][k] = sine*akp + cosine*akq
        values[p][p] = cosine*cosine*app - 2*sine*cosine*apq + sine*sine*aqq
        values[q][q] = sine*sine*app + 2*sine*cosine*apq + cosine*cosine*aqq
        values[p][q] = values[q][p] = 0.0
        for k in range(size):
            vkp, vkq = vectors[k][p], vectors[k][q]
            vectors[k][p] = cosine*vkp - sine*vkq
            vectors[k][q] = sine*vkp + cosine*vkq
    return [values[i][i] for i in range(size)], vectors


def _classical_mds(target):
    size = len(target)
    squared = [[target[i][j] ** 2 for j in range(size)] for i in range(size)]
    row_means = [sum(row) / size for row in squared]
    total_mean = sum(row_means) / size
    gram = [[-0.5 * (squared[i][j] - row_means[i] - row_means[j] + total_mean)
             for j in range(size)] for i in range(size)]
    eigenvalues, eigenvectors = _eigen_symmetric(gram)
    order = sorted(range(size), key=lambda idx: eigenvalues[idx], reverse=True)[:3]
    coords = []
    for i in range(size):
        row = []
        for dimension in range(3):
            if dimension < len(order) and eigenvalues[order[dimension]] > 0.0:
                row.append(eigenvectors[i][order[dimension]]
                           * math.sqrt(eigenvalues[order[dimension]]))
            else:
                row.append(0.0)
        coords.append(row)
    return coords


def _center(coords):
    means = [sum(row[k] for row in coords) / len(coords) for k in range(3)]
    for row in coords:
        for k in range(3):
            row[k] -= means[k]


def _enforce_chirality(coords, constraints):
    if not constraints:
        return
    correct = sum(constraint["sign"] * _volume(
        coords, constraint["center"], constraint["neighbors"]) >= 0.0
        for constraint in constraints)
    # Euclidean distance geometry determines a structure only up to reflection.
    # Select the global handedness without altering any pair distance.
    if correct * 2 < len(constraints):
        for row in coords:
            row[2] = -row[2]


def _refine(coords, target, lower, upper, chirality, iterations=1200):
    size = len(coords)
    _enforce_chirality(coords, chirality)
    for iteration in range(iterations):
        gradients = [[0.0, 0.0, 0.0] for _ in range(size)]
        for i in range(size):
            for j in range(i + 1, size):
                vector = _sub(coords[i], coords[j])
                distance = _norm(vector)
                if distance < 1e-10:
                    vector = [1e-4 * (1+i), 1e-4 * (1+j), 1e-4]
                    distance = _norm(vector)
                desired = target[i][j]
                if distance < lower[i][j]:
                    desired = lower[i][j]
                elif distance > upper[i][j]:
                    desired = upper[i][j]
                error = distance - desired
                weight = 6.0 if (distance < lower[i][j] or distance > upper[i][j]) else 0.10
                factor = weight * error / distance
                for axis in range(3):
                    value = factor * vector[axis]
                    gradients[i][axis] += value
                    gradients[j][axis] -= value
        for constraint in chirality:
            center = constraint["center"]
            first, second, third = constraint["neighbors"]
            sign, minimum = constraint["sign"], constraint["min_volume"]
            origin = coords[center]
            a = _sub(coords[first], origin)
            b = _sub(coords[second], origin)
            c = _sub(coords[third], origin)
            current = _dot(a, _cross(b, c))
            score = sign * current
            if 0.0 <= score < minimum * 1.5:
                deficit = minimum * 1.5 - score
                derivatives = [_cross(b, c), _cross(c, a), _cross(a, b)]
                center_derivative = [-sum(value[axis] for value in derivatives)
                                     for axis in range(3)]
                for atom, derivative in zip(
                        (first, second, third, center),
                        derivatives + [center_derivative]):
                    for axis in range(3):
                        gradients[atom][axis] -= 0.30 * deficit * sign * derivative[axis]
        step = 0.018 / (1.0 + iteration / 180.0)
        for i in range(size):
            for axis in range(3):
                coords[i][axis] -= step * gradients[i][axis]
        if iteration % 60 == 59:
            _center(coords)
    _center(coords)


def _drms(first, second, indices):
    total, count = 0.0, 0
    for offset, i in enumerate(indices):
        for j in indices[offset + 1:]:
            delta = _distance(first[i], first[j]) - _distance(second[i], second[j])
            total += delta * delta
            count += 1
    return math.sqrt(total / max(1, count))


def _rmsd_matrix(conformers, indices):
    size = len(conformers)
    result = [[0.0] * size for _ in range(size)]
    for i in range(size):
        for j in range(i + 1, size):
            value = _drms(conformers[i], conformers[j], indices)
            result[i][j] = result[j][i] = value
    return result


def embed_etkdg(packet):
    """Generate a deterministic bounded distance-geometry ensemble."""
    if not isinstance(packet, dict) or packet.get("schema") != _SCHEMA:
        raise ValueError("unsupported ETKDG packet")
    atomic_numbers = packet.get("atomic_numbers")
    if (not isinstance(atomic_numbers, list) or not 2 <= len(atomic_numbers) <= 192
            or any(not isinstance(value, int) or isinstance(value, bool)
                   or not 1 <= value <= 118 for value in atomic_numbers)):
        raise ValueError("invalid atom list")
    size = len(atomic_numbers)
    bounds = packet.get("pair_bounds")
    if not isinstance(bounds, list) or len(bounds) != size * (size - 1) // 2:
        raise ValueError("pair_bounds must cover every atom pair exactly once")
    lower = [[0.0] * size for _ in range(size)]
    upper = [[0.0] * size for _ in range(size)]
    seen = set()
    for record in bounds:
        if not isinstance(record, dict):
            raise ValueError("invalid pair bound")
        atoms = record.get("atoms")
        if not isinstance(atoms, list) or len(atoms) != 2:
            raise ValueError("invalid bound atom pair")
        i, j = _index(atoms[0], size), _index(atoms[1], size)
        if i == j:
            raise ValueError("bound pair repeats an atom")
        i, j = min(i, j), max(i, j)
        if (i, j) in seen:
            raise ValueError("duplicate pair bound")
        seen.add((i, j))
        low, high = _number(record.get("lower")), _number(record.get("upper"))
        if low < 0.0 or high <= 0.0 or low > high:
            raise ValueError("invalid distance interval")
        lower[i][j] = lower[j][i] = low
        upper[i][j] = upper[j][i] = high
    _smooth(lower, upper)

    chirality_value = packet.get("chiral_constraints")
    if not isinstance(chirality_value, list) or len(chirality_value) > 32:
        raise ValueError("invalid chirality constraints")
    chirality = []
    for record in chirality_value:
        if not isinstance(record, dict):
            raise ValueError("invalid chirality constraint")
        center = _index(record.get("center"), size)
        neighbors = record.get("neighbors")
        if not isinstance(neighbors, list) or len(neighbors) != 3:
            raise ValueError("chirality needs three ordered neighbors")
        neighbors = [_index(value, size) for value in neighbors]
        if len(set([center] + neighbors)) != 4:
            raise ValueError("degenerate chirality indices")
        sign, minimum = record.get("sign"), _number(record.get("min_volume"))
        if sign not in (-1, 1) or isinstance(sign, bool) or minimum <= 0.0:
            raise ValueError("invalid chirality target")
        chirality.append({"center": center, "neighbors": neighbors,
                          "sign": sign, "min_volume": minimum})

    prune_atoms = packet.get("prune_atoms")
    if (not isinstance(prune_atoms, list) or len(prune_atoms) < 2
            or len(set(prune_atoms)) != len(prune_atoms)):
        raise ValueError("invalid pruning atom indices")
    prune_atoms = [_index(value, size) for value in prune_atoms]
    num_confs, seed, max_attempts = (packet.get("num_confs"), packet.get("seed"),
                                     packet.get("max_attempts"))
    if (not isinstance(num_confs, int) or isinstance(num_confs, bool)
            or not 1 <= num_confs <= 32):
        raise ValueError("num_confs out of range")
    if (not isinstance(seed, int) or isinstance(seed, bool)
            or not 0 <= seed <= 2**31 - 1):
        raise ValueError("seed out of range")
    if (not isinstance(max_attempts, int) or isinstance(max_attempts, bool)
            or not num_confs <= max_attempts <= 512):
        raise ValueError("max_attempts out of range")
    prune_rms = _number(packet.get("prune_rms"))
    if not 0.0 <= prune_rms <= 5.0:
        raise ValueError("prune_rms out of range")

    random = _Random(seed)
    conformers, failures, attempts = [], 0, 0
    while attempts < max_attempts and len(conformers) < num_confs:
        attempts += 1
        target = [[0.0] * size for _ in range(size)]
        for i in range(size):
            for j in range(i + 1, size):
                fraction = 0.12 + 0.76 * random.uniform()
                value = lower[i][j] + fraction * (upper[i][j] - lower[i][j])
                target[i][j] = target[j][i] = value
        coords = _classical_mds(target)
        for i, row in enumerate(coords):
            row[2] += 0.025 * (random.uniform() - 0.5) * (1 + (i % 3))
        _refine(coords, target, lower, upper, chirality)
        if any(constraint["sign"] * _volume(
                coords, constraint["center"], constraint["neighbors"])
                < constraint["min_volume"] * 0.95 for constraint in chirality):
            failures += 1
            continue
        if any(_drms(coords, previous, prune_atoms) < prune_rms
               for previous in conformers):
            failures += 1
            continue
        conformers.append(coords)
    failures += max_attempts - attempts if len(conformers) < num_confs else 0
    diagnostics = {
        "attempts": attempts,
        "accepted": len(conformers),
        "triangle_smoothed": True,
        "deterministic_seed": seed,
    }
    return {
        "conformers": conformers,
        "failures": failures,
        "rmsd_matrix": _rmsd_matrix(conformers, prune_atoms),
        "bounds": {"lower": lower, "upper": upper},
        "diagnostics": diagnostics,
    }
