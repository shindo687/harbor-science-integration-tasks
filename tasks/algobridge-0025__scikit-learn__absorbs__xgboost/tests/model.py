"""Shared protocol helpers for the locked reference and candidate runners."""

from __future__ import annotations

import math

import numpy as np


def jsonify(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): jsonify(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonify(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("protocol output must be finite")
    return value


def stable_sigmoid(margin):
    margin = np.asarray(margin, dtype=float)
    result = np.empty_like(margin)
    positive = margin >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-margin[positive]))
    exponential = np.exp(margin[~positive])
    result[~positive] = exponential / (1.0 + exponential)
    return result


def weighted_loss(objective, y, margin, weight):
    y = np.asarray(y, dtype=np.float32).astype(float)
    margin = np.asarray(margin, dtype=np.float32).astype(float)
    weight = np.asarray(weight, dtype=np.float32).astype(float)
    if objective == "squared_error":
        values = 0.5 * np.square(margin - y)
    else:
        values = np.logaddexp(0.0, margin) - y * margin
    return float(np.average(values, weights=weight))


def normalize_xgboost_tree(raw):
    """Convert one JSON dump tree into the candidate's stable schema."""

    def convert(node, depth, canonical_id):
        cover = float(node["cover"])
        if "leaf" in node:
            return {
                "node_id": canonical_id,
                "depth": depth,
                "leaf": float(node["leaf"]),
                "cover": cover,
            }
        children = {int(child["nodeid"]): child for child in node["children"]}
        yes = int(node["yes"])
        no = int(node["no"])
        missing = int(node["missing"])
        feature = str(node["split"])
        if not feature.startswith("f") or not feature[1:].isdigit():
            raise ValueError(f"unexpected feature name: {feature}")
        return {
            "node_id": canonical_id,
            "depth": depth,
            "feature": int(feature[1:]),
            "threshold": float(node["split_condition"]),
            "missing": "left" if missing == yes else "right",
            "gain": float(node["gain"]),
            "cover": cover,
            "left": convert(children[yes], depth + 1, 2 * canonical_id + 1),
            "right": convert(children[no], depth + 1, 2 * canonical_id + 2),
        }

    return convert(raw, 0, 0)


def walk_splits(tree):
    if "leaf" in tree:
        return
    yield tree
    yield from walk_splits(tree["left"])
    yield from walk_splits(tree["right"])
