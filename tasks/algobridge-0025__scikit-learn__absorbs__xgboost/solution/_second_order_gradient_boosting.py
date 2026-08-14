"""Bounded exact second-order gradient boosted trees.

This module is an independent implementation of the public numerical contract
used by the task.  It intentionally supports only small dense CPU datasets.
"""

from __future__ import annotations

import math
import numbers

import numpy as np

from sklearn.base import BaseEstimator


_EPS = np.float32(1e-6)


def _float32(value):
    return float(np.float32(value))


def _sum(values, indices):
    return sum((float(values[index]) for index in indices), 0.0)


def _threshold_l1(gradient, alpha):
    if gradient > alpha:
        return gradient - alpha
    if gradient < -alpha:
        return gradient + alpha
    return 0.0


def _weight(gradient, hessian, reg_lambda, reg_alpha):
    if hessian <= 0.0:
        return 0.0
    return -_threshold_l1(gradient, reg_alpha) / (
        hessian + reg_lambda
    )


def _score(gradient, hessian, reg_lambda, reg_alpha):
    if hessian <= 0.0:
        return 0.0
    adjusted = _threshold_l1(gradient, reg_alpha)
    return adjusted * adjusted / (hessian + reg_lambda)


class _ExactTreeBuilder:
    def __init__(
        self,
        X,
        gradient,
        hessian,
        *,
        max_depth,
        learning_rate,
        reg_lambda,
        reg_alpha,
        min_split_loss,
    ):
        self.X = X
        self.gradient = gradient
        self.hessian = hessian
        self.max_depth = max_depth
        self.learning_rate = np.float32(learning_rate)
        self.reg_lambda = float(np.float32(reg_lambda))
        self.reg_alpha = float(np.float32(reg_alpha))
        self.min_split_loss = float(np.float32(min_split_loss))

    def _stats(self, indices):
        return (
            _sum(self.gradient, indices),
            _sum(self.hessian, indices),
        )

    def _leaf_value(self, gradient, hessian):
        base = np.float32(
            _weight(
                gradient,
                hessian,
                self.reg_lambda,
                self.reg_alpha,
            )
        )
        return _float32(np.float32(base * self.learning_rate))

    def _consider(
        self,
        best,
        *,
        feature,
        threshold,
        missing,
        left_gradient,
        left_hessian,
        right_gradient,
        right_hessian,
        root_gain,
    ):
        if left_hessian <= 0.0 or right_hessian <= 0.0:
            return best
        gain = np.float32(
            _score(
                left_gradient,
                left_hessian,
                self.reg_lambda,
                self.reg_alpha,
            )
            + _score(
                right_gradient,
                right_hessian,
                self.reg_lambda,
                self.reg_alpha,
            )
            - root_gain
        )
        # The locked exact updater keeps the first equal-gain candidate. Feature
        # enumeration is ascending, as are thresholds in the forward scan.
        if not math.isfinite(float(gain)) or not float(gain) > best["gain"]:
            return best
        return {
            "gain": float(gain),
            "feature": int(feature),
            "threshold": _float32(threshold),
            "missing": missing,
        }

    def _best_split(self, indices, total_gradient, total_hessian):
        root_gain = np.float32(
            _score(
                total_gradient,
                total_hessian,
                self.reg_lambda,
                self.reg_alpha,
            )
        )
        best = {"gain": 0.0}
        for feature in range(self.X.shape[1]):
            values = self.X[indices, feature]
            observed_mask = ~np.isnan(values)
            observed_indices = indices[observed_mask]
            if observed_indices.size == 0:
                continue
            order = np.argsort(
                self.X[observed_indices, feature], kind="stable"
            )
            ordered = observed_indices[order]
            ordered_values = self.X[ordered, feature]

            # The exact updater skips its forward scan for a fully dense column
            # and for an indicator-like constant observed column. Its backward
            # scan is always enabled under the learned default-direction mode.
            global_values = self.X[:, feature]
            global_observed = global_values[~np.isnan(global_values)]
            need_forward = (
                global_observed.size < global_values.size
                and global_observed.size > 0
                and global_observed[0] != global_observed[-1]
            )

            # Forward scan: observed prefix goes left and missing values right.
            left_gradient = 0.0
            left_hessian = 0.0
            cursor = 0
            while cursor < ordered.size:
                value = ordered_values[cursor]
                stop = cursor + 1
                while stop < ordered.size and ordered_values[stop] == value:
                    stop += 1
                for row in ordered[cursor:stop]:
                    left_gradient += float(self.gradient[row])
                    left_hessian += float(self.hessian[row])
                if stop < ordered.size:
                    next_value = ordered_values[stop]
                    threshold = np.float32(
                        np.float32(value + next_value) * np.float32(0.5)
                    )
                    if threshold == next_value:
                        threshold = value
                    if need_forward:
                        best = self._consider(
                            best,
                            feature=feature,
                            threshold=threshold,
                            missing="right",
                            left_gradient=left_gradient,
                            left_hessian=left_hessian,
                            right_gradient=total_gradient - left_gradient,
                            right_hessian=total_hessian - left_hessian,
                            root_gain=root_gain,
                        )
                cursor = stop

            # The end candidate separates missing from all observed values.
            last_value = ordered_values[-1]
            threshold = np.float32(
                last_value + np.float32(abs(float(last_value)) + float(_EPS))
            )
            if need_forward:
                best = self._consider(
                    best,
                    feature=feature,
                    threshold=threshold,
                    missing="right",
                    left_gradient=left_gradient,
                    left_hessian=left_hessian,
                    right_gradient=total_gradient - left_gradient,
                    right_hessian=total_hessian - left_hessian,
                    root_gain=root_gain,
                )

            # Backward scan: observed suffix goes right and missing values left.
            right_gradient = 0.0
            right_hessian = 0.0
            cursor = ordered.size
            while cursor > 0:
                value = ordered_values[cursor - 1]
                start = cursor - 1
                while start > 0 and ordered_values[start - 1] == value:
                    start -= 1
                for row in ordered[start:cursor]:
                    right_gradient += float(self.gradient[row])
                    right_hessian += float(self.hessian[row])
                if start > 0:
                    previous_value = ordered_values[start - 1]
                    threshold = np.float32(
                        np.float32(previous_value + value) * np.float32(0.5)
                    )
                    if threshold == value:
                        threshold = previous_value
                    best = self._consider(
                        best,
                        feature=feature,
                        threshold=threshold,
                        missing="left",
                        left_gradient=total_gradient - right_gradient,
                        left_hessian=total_hessian - right_hessian,
                        right_gradient=right_gradient,
                        right_hessian=right_hessian,
                        root_gain=root_gain,
                    )
                cursor = start

            first_value = ordered_values[0]
            threshold = np.float32(
                first_value
                - np.float32(abs(float(first_value)) + float(_EPS))
            )
            best = self._consider(
                best,
                feature=feature,
                threshold=threshold,
                missing="left",
                left_gradient=total_gradient - right_gradient,
                left_hessian=total_hessian - right_hessian,
                right_gradient=right_gradient,
                right_hessian=right_hessian,
                root_gain=root_gain,
            )
        return best

    def _build(self, indices, node_id, depth):
        gradient, hessian = self._stats(indices)
        leaf = {
            "node_id": int(node_id),
            "depth": int(depth),
            "leaf": self._leaf_value(gradient, hessian),
            "cover": _float32(hessian),
        }
        if depth >= self.max_depth:
            return leaf
        best = self._best_split(indices, gradient, hessian)
        if not best["gain"] > float(_EPS):
            return leaf
        feature = best["feature"]
        values = self.X[indices, feature]
        missing = np.isnan(values)
        go_left = values < np.float32(best["threshold"])
        if best["missing"] == "left":
            go_left = go_left | missing
        else:
            go_left = go_left & ~missing
        left_indices = indices[go_left]
        right_indices = indices[~go_left]
        if left_indices.size == 0 or right_indices.size == 0:
            return leaf
        return {
            "node_id": int(node_id),
            "depth": int(depth),
            "feature": int(feature),
            "threshold": _float32(best["threshold"]),
            "missing": best["missing"],
            "gain": _float32(best["gain"]),
            "cover": _float32(hessian),
            "_leaf": leaf["leaf"],
            "left": self._build(left_indices, 2 * node_id + 1, depth + 1),
            "right": self._build(right_indices, 2 * node_id + 2, depth + 1),
        }

    def _prune(self, node):
        if "leaf" in node:
            return node
        node["left"] = self._prune(node["left"])
        node["right"] = self._prune(node["right"])
        if (
            "leaf" in node["left"]
            and "leaf" in node["right"]
            and node["gain"] < self.min_split_loss
        ):
            return {
                "node_id": node["node_id"],
                "depth": node["depth"],
                "leaf": node["_leaf"],
                "cover": node["cover"],
            }
        node.pop("_leaf", None)
        return node

    def build(self):
        indices = np.arange(self.X.shape[0], dtype=np.int64)
        return self._prune(self._build(indices, 0, 0))


def _tree_predict_one(tree, row):
    node = tree
    while "leaf" not in node:
        value = row[node["feature"]]
        if np.isnan(value):
            node = node[node["missing"]]
        elif value < np.float32(node["threshold"]):
            node = node["left"]
        else:
            node = node["right"]
    return np.float32(node["leaf"])


def _tree_predict(tree, X):
    return np.asarray([_tree_predict_one(tree, row) for row in X], dtype=np.float32)


def _sigmoid(margin):
    margin = np.asarray(margin, dtype=float)
    result = np.empty_like(margin)
    positive = margin >= 0
    result[positive] = 1.0 / (1.0 + np.exp(-margin[positive]))
    exponential = np.exp(margin[~positive])
    result[~positive] = exponential / (1.0 + exponential)
    return result


def _walk_splits(tree):
    if "leaf" in tree:
        return
    yield tree
    yield from _walk_splits(tree["left"])
    yield from _walk_splits(tree["right"])


class SecondOrderGradientBoosting(BaseEstimator):
    """Small deterministic exact second-order boosted-tree estimator."""

    def __init__(
        self,
        *,
        objective="squared_error",
        n_estimators=6,
        max_depth=2,
        learning_rate=0.3,
        reg_lambda=1.0,
        reg_alpha=0.0,
        min_split_loss=0.0,
    ):
        self.objective = objective
        self.n_estimators = n_estimators
        self.max_depth = max_depth
        self.learning_rate = learning_rate
        self.reg_lambda = reg_lambda
        self.reg_alpha = reg_alpha
        self.min_split_loss = min_split_loss

    def _validate_parameters(self):
        if self.objective not in {"squared_error", "logistic"}:
            raise ValueError("unsupported objective")
        if (
            not isinstance(self.n_estimators, numbers.Integral)
            or isinstance(self.n_estimators, bool)
            or not 1 <= int(self.n_estimators) <= 12
        ):
            raise ValueError("n_estimators must be an integer in [1, 12]")
        if (
            not isinstance(self.max_depth, numbers.Integral)
            or isinstance(self.max_depth, bool)
            or not 1 <= int(self.max_depth) <= 3
        ):
            raise ValueError("max_depth must be an integer in [1, 3]")
        for name, value in (
            ("learning_rate", self.learning_rate),
            ("reg_lambda", self.reg_lambda),
            ("reg_alpha", self.reg_alpha),
            ("min_split_loss", self.min_split_loss),
        ):
            if not isinstance(value, numbers.Real) or not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not 0.0 <= float(self.learning_rate) <= 1.0:
            raise ValueError("learning_rate must be in [0, 1]")
        if any(
            float(value) < 0.0
            for value in (self.reg_lambda, self.reg_alpha, self.min_split_loss)
        ):
            raise ValueError("regularizers must be non-negative")

    @staticmethod
    def _validate_X(X, *, fitted_features=None):
        try:
            array = np.asarray(X, dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise ValueError("X must be a dense numeric array") from error
        if array.ndim != 2:
            raise ValueError("X must be two-dimensional")
        if fitted_features is None:
            if not 4 <= array.shape[0] <= 256 or not 1 <= array.shape[1] <= 16:
                raise ValueError("X shape is outside the bounded contract")
        elif array.shape[1] != fitted_features:
            raise ValueError("X has the wrong number of features")
        if np.isinf(array).any():
            raise ValueError("X must not contain infinities")
        if np.any(np.all(np.isnan(array), axis=0)):
            raise ValueError("each feature needs at least one observed value")
        return np.asarray(array, dtype=np.float32)

    @staticmethod
    def _validate_weight(sample_weight, rows):
        if sample_weight is None:
            return np.ones(rows, dtype=np.float32)
        try:
            weight = np.asarray(sample_weight, dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise ValueError("sample_weight must be numeric") from error
        if (
            weight.ndim != 1
            or weight.shape[0] != rows
            or not np.all(np.isfinite(weight))
            or np.any(weight <= 0.0)
        ):
            raise ValueError("sample_weight must be finite and strictly positive")
        return np.asarray(weight, dtype=np.float32)

    def _loss(self, y, margin, weight):
        margin64 = np.asarray(margin, dtype=np.float64)
        y64 = np.asarray(y, dtype=np.float64)
        weight64 = np.asarray(weight, dtype=np.float64)
        if self.objective == "squared_error":
            values = 0.5 * np.square(margin64 - y64)
        else:
            values = np.logaddexp(0.0, margin64) - y64 * margin64
        return float(np.average(values, weights=weight64))

    def _gradient(self, margin, y, weight):
        margin = np.asarray(margin, dtype=np.float32)
        y = np.asarray(y, dtype=np.float32)
        weight = np.asarray(weight, dtype=np.float32)
        if self.objective == "squared_error":
            gradient = np.asarray((margin - y) * weight, dtype=np.float32)
            hessian = np.asarray(weight, dtype=np.float32)
        else:
            probability = np.asarray(
                np.float32(1.0)
                / (np.float32(1.0) + np.exp(-margin)),
                dtype=np.float32,
            )
            gradient = np.asarray((probability - y) * weight, dtype=np.float32)
            hessian = np.asarray(
                np.maximum(
                    probability * (np.float32(1.0) - probability),
                    np.float32(1e-16),
                )
                * weight,
                dtype=np.float32,
            )
        return gradient, hessian

    def fit(self, X, y, sample_weight=None):
        self._validate_parameters()
        X = self._validate_X(X)
        try:
            y = np.asarray(y, dtype=np.float64)
        except (TypeError, ValueError) as error:
            raise ValueError("y must be numeric") from error
        if y.ndim != 1 or y.shape[0] != X.shape[0] or not np.all(np.isfinite(y)):
            raise ValueError("y must be a finite vector aligned with X")
        if self.objective == "logistic" and not np.all((y == 0.0) | (y == 1.0)):
            raise ValueError("logistic y must contain only 0 and 1")
        weight = self._validate_weight(sample_weight, X.shape[0])
        y32 = np.asarray(y, dtype=np.float32)
        margin = np.zeros(X.shape[0], dtype=np.float32)

        self.n_features_in_ = int(X.shape[1])
        self.trees_ = []
        self.feature_gains_ = np.zeros(self.n_features_in_, dtype=float)
        losses = [self._loss(y32, margin, weight)]
        for _ in range(int(self.n_estimators)):
            gradient, hessian = self._gradient(margin, y32, weight)
            tree = _ExactTreeBuilder(
                X,
                gradient,
                hessian,
                max_depth=int(self.max_depth),
                learning_rate=float(self.learning_rate),
                reg_lambda=float(self.reg_lambda),
                reg_alpha=float(self.reg_alpha),
                min_split_loss=float(self.min_split_loss),
            ).build()
            self.trees_.append(tree)
            for split in _walk_splits(tree):
                self.feature_gains_[split["feature"]] += split["gain"]
            margin = np.asarray(margin + _tree_predict(tree, X), dtype=np.float32)
            losses.append(self._loss(y32, margin, weight))
        self.training_loss_ = np.asarray(losses, dtype=float)
        self._is_fitted = True
        if self.objective == "logistic":
            self.classes_ = np.asarray([0, 1])
        return self

    def _check_fitted(self):
        if not getattr(self, "_is_fitted", False):
            raise ValueError("estimator is not fitted")

    def decision_function(self, X):
        self._check_fitted()
        X = self._validate_X(X, fitted_features=self.n_features_in_)
        margin = np.zeros(X.shape[0], dtype=np.float32)
        for tree in self.trees_:
            margin = np.asarray(margin + _tree_predict(tree, X), dtype=np.float32)
        return np.asarray(margin, dtype=float)

    def predict_proba(self, X):
        if self.objective != "logistic":
            raise ValueError("predict_proba is available only for logistic objective")
        positive = _sigmoid(self.decision_function(X))
        return np.column_stack([1.0 - positive, positive])

    def predict(self, X):
        margin = self.decision_function(X)
        if self.objective == "squared_error":
            return margin
        return (_sigmoid(margin) >= 0.5).astype(int)
