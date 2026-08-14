"""Independent mathematical oracle for the bounded deterministic UPGMA tree."""

from __future__ import annotations

from common import Node, _BLOSUM62


def _substitution(left, right, alphabet):
    if alphabet == "dna":
        return 2 if left == right else -1
    return _BLOSUM62.get((left, right), 1 if left == right else -1)


def _best(values):
    # Stable lower-state tie break, matching the documented deterministic DP.
    return max(range(3), key=lambda state: (values[state], -state))


def _pair_alignment(left, right, alphabet, gap_open, gap_extend):
    rows = len(left) + 1
    columns = len(right) + 1
    negative = -1.0e300
    score = [[[negative] * columns for _ in range(rows)] for _ in range(3)]
    previous = [[[None] * columns for _ in range(rows)] for _ in range(3)]
    score[0][0][0] = 0.0
    for i in range(rows):
        for j in range(columns):
            if i and j:
                values = [score[state][i - 1][j - 1] for state in range(3)]
                state = _best(values)
                score[0][i][j] = values[state] + _substitution(
                    left[i - 1], right[j - 1], alphabet
                )
                previous[0][i][j] = state
            if i:
                values = [
                    score[0][i - 1][j] - gap_open,
                    score[1][i - 1][j] - gap_extend,
                    score[2][i - 1][j] - gap_open,
                ]
                state = _best(values)
                score[1][i][j] = values[state]
                previous[1][i][j] = state
            if j:
                values = [
                    score[0][i][j - 1] - gap_open,
                    score[1][i][j - 1] - gap_open,
                    score[2][i][j - 1] - gap_extend,
                ]
                state = _best(values)
                score[2][i][j] = values[state]
                previous[2][i][j] = state

    state = _best([score[item][-1][-1] for item in range(3)])
    operations = []
    i = len(left)
    j = len(right)
    while i or j:
        operations.append(state)
        old = previous[state][i][j]
        if old is None:
            raise RuntimeError("independent pairwise DP traceback failed")
        if state == 0:
            i -= 1
            j -= 1
        elif state == 1:
            i -= 1
        else:
            j -= 1
        state = old
    operations.reverse()
    aligned_left = []
    aligned_right = []
    i = 0
    j = 0
    for operation in operations:
        aligned_left.append("-" if operation == 2 else left[i])
        aligned_right.append("-" if operation == 1 else right[j])
        if operation != 2:
            i += 1
        if operation != 1:
            j += 1
    return "".join(aligned_left), "".join(aligned_right)


def _distance(left, right, alphabet, gap_open, gap_extend):
    aligned_left, aligned_right = _pair_alignment(
        left, right, alphabet, gap_open, gap_extend
    )
    comparable = [
        (a, b) for a, b in zip(aligned_left, aligned_right)
        if a != "-" and b != "-"
    ]
    matches = sum(a == b for a, b in comparable)
    return 1.0 - matches / max(1, len(comparable))


def bounded_upgma(records, alphabet, gap_open, gap_extend):
    records = sorted(records)
    clusters = {
        i: {
            "members": (name,),
            "size": 1,
            "height": 0.0,
            "node": Node(name=name),
        }
        for i, (name, _) in enumerate(records)
    }
    sequences = dict(records)
    distances = {}
    for i in clusters:
        for j in clusters:
            if i < j:
                distances[i, j] = _distance(
                    sequences[records[i][0]], sequences[records[j][0]],
                    alphabet, gap_open, gap_extend
                )
    next_id = len(clusters)
    while len(clusters) > 1:
        choices = []
        ids = sorted(clusters)
        for position, left_id in enumerate(ids):
            for right_id in ids[position + 1 :]:
                choices.append(
                    (
                        distances[min(left_id, right_id), max(left_id, right_id)],
                        clusters[left_id]["members"],
                        clusters[right_id]["members"],
                        left_id,
                        right_id,
                    )
                )
        distance, _, _, left_id, right_id = min(choices)
        left = clusters[left_id]
        right = clusters[right_id]
        height = max(distance / 2.0, left["height"], right["height"])
        left["node"].length = height - left["height"]
        right["node"].length = height - right["height"]
        merged = {
            "members": tuple(sorted(left["members"] + right["members"])),
            "size": left["size"] + right["size"],
            "height": height,
            "node": Node(children=[left["node"], right["node"]]),
        }
        for other_id, other in list(clusters.items()):
            if other_id in (left_id, right_id):
                continue
            left_distance = distances[min(left_id, other_id), max(left_id, other_id)]
            right_distance = distances[min(right_id, other_id), max(right_id, other_id)]
            distances[min(next_id, other_id), max(next_id, other_id)] = (
                left["size"] * left_distance + right["size"] * right_distance
            ) / merged["size"]
        clusters.pop(left_id)
        clusters.pop(right_id)
        clusters[next_id] = merged
        next_id += 1
    return next(iter(clusters.values()))["node"]

