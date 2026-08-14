#!/usr/bin/env python3
"""Run the locked XGBoost exact reference on JSON cases."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import xgboost as xgb

from model import jsonify, normalize_xgboost_tree, stable_sigmoid, walk_splits, weighted_loss


def run_case(case):
    X = np.asarray(case["X"], dtype=np.float64)
    y = np.asarray(case["y"], dtype=np.float64)
    test_X = np.asarray(case.get("test_X", case["X"]), dtype=np.float64)
    weight = np.asarray(
        case.get("sample_weight", np.ones(X.shape[0])), dtype=np.float64
    )
    params = case["params"]
    objective = params["objective"]
    dtrain = xgb.DMatrix(X, label=y, weight=weight)
    dtest = xgb.DMatrix(test_X)
    xgb_params = {
        "objective": (
            "reg:squarederror" if objective == "squared_error" else "binary:logistic"
        ),
        "tree_method": "exact",
        "nthread": 1,
        "seed": 0,
        "verbosity": 0,
        "max_depth": int(params["max_depth"]),
        "eta": float(params["learning_rate"]),
        "lambda": float(params["reg_lambda"]),
        "alpha": float(params["reg_alpha"]),
        "gamma": float(params["min_split_loss"]),
        "min_child_weight": 0.0,
        "max_delta_step": 0.0,
        "subsample": 1.0,
        "colsample_bytree": 1.0,
        "colsample_bylevel": 1.0,
        "colsample_bynode": 1.0,
        "base_score": 0.0 if objective == "squared_error" else 0.5,
        "boost_from_average": 0,
        "disable_default_eval_metric": 1,
    }
    rounds = int(params["n_estimators"])
    booster = xgb.train(xgb_params, dtrain, num_boost_round=rounds)
    trees = [
        normalize_xgboost_tree(json.loads(item))
        for item in booster.get_dump(dump_format="json", with_stats=True)
    ]
    feature_gains = np.zeros(X.shape[1], dtype=float)
    for tree in trees:
        for split in walk_splits(tree):
            feature_gains[split["feature"]] += split["gain"]

    losses = [weighted_loss(objective, y, np.zeros(X.shape[0]), weight)]
    for end in range(1, rounds + 1):
        stage_margin = booster.predict(
            dtrain, output_margin=True, iteration_range=(0, end)
        )
        losses.append(weighted_loss(objective, y, stage_margin, weight))
    margin = np.asarray(booster.predict(dtest, output_margin=True), dtype=float)
    if objective == "squared_error":
        prediction = margin
        probability = None
    else:
        positive = stable_sigmoid(margin)
        probability = np.column_stack([1.0 - positive, positive])
        prediction = (positive >= 0.5).astype(int)
    return {
        "name": case["name"],
        "trees": trees,
        "feature_gains": feature_gains,
        "training_loss": losses,
        "margin": margin,
        "prediction": prediction,
        "probability": probability,
    }


def main():
    source = Path(sys.argv[1])
    destination = Path(sys.argv[2])
    cases = json.loads(source.read_text(encoding="utf-8"))
    result = {
        "reference": "XGBoost exact a3e3df59b83e1f230bb238c99dbaf63d8382ed24",
        "version": xgb.__version__,
        "cases": [run_case(case) for case in cases],
    }
    destination.write_text(
        json.dumps(jsonify(result), allow_nan=False, sort_keys=True),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
