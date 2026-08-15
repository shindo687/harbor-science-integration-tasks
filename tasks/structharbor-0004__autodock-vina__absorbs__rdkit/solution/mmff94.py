"""Clean-room bounded MMFF94 fixed-geometry energy evaluator."""

from __future__ import annotations

import math


_SCHEMA = "structharbor-vina-rdkit-mmff94-v1"
_C = 143.9325
_DEG = math.pi / 180.0
_OUTPUT = (
    "bond", "angle", "stretch_bend", "out_of_plane", "torsion",
    "van_der_waals", "electrostatic",
)
_LIMITS = {
    "bonds": 512, "angles": 4096, "stretch_bends": 4096,
    "out_of_plane": 4096, "torsions": 8192, "nonbonded": 32768,
}


def _number(value):
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
            or not math.isfinite(value)):
        raise ValueError("expected a finite number")
    return float(value)


def _vector(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("expected a Cartesian three-vector")
    return tuple(_number(item) for item in value)


def _sub(first, second):
    return tuple(first[i] - second[i] for i in range(3))


def _dot(first, second):
    return sum(first[i] * second[i] for i in range(3))


def _cross(first, second):
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _norm(value):
    result = math.sqrt(_dot(value, value))
    if result <= 1.0e-12:
        raise ValueError("degenerate geometry")
    return result


def _unit(value):
    length = _norm(value)
    return tuple(item / length for item in value)


def _clip(value):
    return max(-1.0, min(1.0, value))


def _records(packet, name):
    records = packet.get(name)
    if not isinstance(records, list) or len(records) > _LIMITS[name]:
        raise ValueError("invalid interaction records")
    if any(not isinstance(record, dict) for record in records):
        raise ValueError("interaction records must be objects")
    return records


def _atoms(record, count, atom_count):
    value = record.get("atoms")
    if not isinstance(value, list) or len(value) != count:
        raise ValueError("invalid atom tuple")
    result = []
    for index in value:
        if (not isinstance(index, int) or isinstance(index, bool)
                or not 0 <= index < atom_count):
            raise ValueError("atom index out of range")
        result.append(index)
    if len(set(result)) != len(result):
        raise ValueError("atom tuple contains duplicates")
    return result


def _parameters(record, names):
    return [_number(record.get(name)) for name in names]


def _distance(positions, first, second):
    return _norm(_sub(positions[first], positions[second]))


def _angle(positions, i, j, k):
    first = _sub(positions[i], positions[j])
    second = _sub(positions[k], positions[j])
    cosine = _clip(_dot(first, second) / (_norm(first) * _norm(second)))
    return math.acos(cosine), cosine


def score_mmff94(packet):
    """Evaluate a validated, preparameterized MMFF94 interaction packet."""
    if not isinstance(packet, dict) or packet.get("schema") != _SCHEMA:
        raise ValueError("unsupported MMFF94 packet")
    positions_value = packet.get("positions")
    if (not isinstance(positions_value, list)
            or not 1 <= len(positions_value) <= 256):
        raise ValueError("positions must contain 1 through 256 atoms")
    positions = [_vector(value) for value in positions_value]
    atom_count = len(positions)
    energy = {name: 0.0 for name in _OUTPUT}

    for record in _records(packet, "bonds"):
        i, j = _atoms(record, 2, atom_count)
        kb, r0 = _parameters(record, ("kb", "r0"))
        if kb < 0.0 or r0 <= 0.0:
            raise ValueError("invalid bond parameters")
        delta = _distance(positions, i, j) - r0
        energy["bond"] += 0.5 * _C * kb * delta * delta * (
            1.0 - 2.0 * delta + (7.0 / 3.0) * delta * delta
        )

    for record in _records(packet, "angles"):
        i, j, k = _atoms(record, 3, atom_count)
        ka, theta0 = _parameters(record, ("ka", "theta0"))
        linear = record.get("linear")
        if ka < 0.0 or not 0.0 < theta0 <= 180.0 or not isinstance(linear, bool):
            raise ValueError("invalid angle parameters")
        radians, cosine = _angle(positions, i, j, k)
        if linear:
            value = _C * ka * (1.0 + cosine)
        else:
            delta = math.degrees(radians) - theta0
            value = 0.5 * _C * _DEG * _DEG * ka * delta * delta * (
                1.0 - 0.006981317 * delta
            )
        energy["angle"] += value

    for record in _records(packet, "stretch_bends"):
        i, j, k = _atoms(record, 3, atom_count)
        kba_ijk, kba_kji, r0_ij, r0_jk, theta0 = _parameters(
            record, ("kba_ijk", "kba_kji", "r0_ij", "r0_jk", "theta0")
        )
        if r0_ij <= 0.0 or r0_jk <= 0.0 or not 0.0 < theta0 < 180.0:
            raise ValueError("invalid stretch-bend parameters")
        radians, _ = _angle(positions, i, j, k)
        delta_theta = math.degrees(radians) - theta0
        energy["stretch_bend"] += _C * _DEG * delta_theta * (
            kba_ijk * (_distance(positions, i, j) - r0_ij)
            + kba_kji * (_distance(positions, j, k) - r0_jk)
        )

    for record in _records(packet, "out_of_plane"):
        i, j, k, l = _atoms(record, 4, atom_count)
        koop, = _parameters(record, ("koop",))
        rji = _unit(_sub(positions[i], positions[j]))
        rjk = _unit(_sub(positions[k], positions[j]))
        rjl = _unit(_sub(positions[l], positions[j]))
        normal = _unit(_cross(rji, rjk))
        chi = math.degrees(math.asin(_clip(_dot(normal, rjl))))
        energy["out_of_plane"] += 0.5 * _C * _DEG * _DEG * koop * chi * chi

    for record in _records(packet, "torsions"):
        i, j, k, l = _atoms(record, 4, atom_count)
        v1, v2, v3 = _parameters(record, ("v1", "v2", "v3"))
        r1 = _sub(positions[i], positions[j])
        r2 = _sub(positions[k], positions[j])
        r3 = _sub(positions[j], positions[k])
        r4 = _sub(positions[l], positions[k])
        first, second = _cross(r1, r2), _cross(r3, r4)
        cosine = _clip(_dot(first, second) / (_norm(first) * _norm(second)))
        cosine2 = 2.0 * cosine * cosine - 1.0
        cosine3 = cosine * (2.0 * cosine2 - 1.0)
        energy["torsion"] += 0.5 * (
            v1 * (1.0 + cosine) + v2 * (1.0 - cosine2)
            + v3 * (1.0 + cosine3)
        )

    for record in _records(packet, "nonbonded"):
        i, j = _atoms(record, 2, atom_count)
        r_star, epsilon, charge_term = _parameters(
            record, ("r_star", "epsilon", "charge_term")
        )
        model, is_1_4 = record.get("dielectric_model"), record.get("is_1_4")
        if (r_star <= 0.0 or epsilon < 0.0 or model not in (1, 2)
                or not isinstance(model, int) or isinstance(model, bool)
                or not isinstance(is_1_4, bool)):
            raise ValueError("invalid nonbonded parameters")
        distance = _distance(positions, i, j)
        distance7 = distance ** 7
        r_star7 = r_star ** 7
        first = (1.07 * r_star / (distance + 0.07 * r_star)) ** 7
        second = 1.12 * r_star7 / (distance7 + 0.12 * r_star7) - 2.0
        energy["van_der_waals"] += epsilon * first * second
        corrected = distance + 0.05
        if model == 2:
            corrected *= corrected
        energy["electrostatic"] += (
            332.0716 * charge_term / corrected * (0.75 if is_1_4 else 1.0)
        )

    result = {name: energy[name] for name in _OUTPUT}
    result["total"] = sum(result.values())
    if any(not math.isfinite(value) for value in result.values()):
        raise ValueError("non-finite MMFF94 energy")
    return result
