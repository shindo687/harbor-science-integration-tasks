"""Deterministic dense classic SMOTE resampling."""

# Authors: The scikit-learn developers
# SPDX-License-Identifier: BSD-3-Clause

from numbers import Integral, Real

import numpy as np

from sklearn.base import BaseEstimator
from sklearn.neighbors import NearestNeighbors
from sklearn.utils.multiclass import check_classification_targets
from sklearn.utils.validation import (
    FLOAT_DTYPES,
    _check_sample_weight,
    check_random_state,
    validate_data,
)


class SMOTE(BaseEstimator):
    """Synthetic Minority Over-sampling Technique for dense numeric data.

    Parameters
    ----------
    sampling_strategy : str, dict or float, default="auto"
        Classes and target counts to over-sample. A float is a minority to
        majority ratio and is valid only for binary targets.

    random_state : int, RandomState instance or None, default=None
        Controls parent-neighbor selection and interpolation.

    k_neighbors : int, default=5
        Number of same-class nearest neighbors available for interpolation.
    """

    def __init__(self, *, sampling_strategy="auto", random_state=None, k_neighbors=5):
        self.sampling_strategy = sampling_strategy
        self.random_state = random_state
        self.k_neighbors = k_neighbors

    @staticmethod
    def _class_statistics(y):
        classes, counts = np.unique(y, return_counts=True)
        if classes.size < 2:
            raise ValueError("y needs to contain more than one class")
        return classes, counts

    def _resolve_sampling_strategy(self, y):
        classes, counts = self._class_statistics(y)
        majority_count = int(np.max(counts))
        majority_index = int(np.argmax(counts))
        minority_index = int(np.argmin(counts))
        strategy = self.sampling_strategy

        if isinstance(strategy, str):
            valid = {
                "auto",
                "minority",
                "not minority",
                "not majority",
                "all",
            }
            if strategy not in valid:
                raise ValueError(f"unsupported sampling_strategy: {strategy!r}")
            if strategy == "auto":
                strategy = "not majority"
            selected = []
            for index in range(len(classes)):
                if strategy == "minority" and index == minority_index:
                    selected.append(index)
                elif strategy == "not minority" and index != minority_index:
                    selected.append(index)
                elif strategy == "not majority" and index != majority_index:
                    selected.append(index)
                elif strategy == "all":
                    selected.append(index)
            return {
                classes[index]: majority_count - int(counts[index])
                for index in selected
            }

        if isinstance(strategy, dict):
            requested = strategy
            known = set(classes.tolist())
            unknown = set(requested) - known
            if unknown:
                raise ValueError(f"target classes are not present in y: {unknown}")
            result = {}
            for class_label, count in zip(classes, counts, strict=True):
                scalar_label = class_label.item() if isinstance(class_label, np.generic) else class_label
                if scalar_label not in requested:
                    continue
                target = requested[scalar_label]
                if not isinstance(target, Integral) or isinstance(target, (bool, np.bool_)):
                    raise TypeError("dictionary target counts must be integers")
                if int(target) < int(count):
                    raise ValueError("target count cannot be below the current class count")
                result[class_label] = int(target) - int(count)
            return result

        if isinstance(strategy, Real) and not isinstance(strategy, Integral):
            ratio = float(strategy)
            if not 0.0 < ratio <= 1.0:
                raise ValueError("float sampling_strategy must be in (0, 1]")
            if len(classes) != 2:
                raise ValueError("float sampling_strategy is only valid for binary y")
            generated = int(majority_count * ratio - int(counts[minority_index]))
            if generated <= 0:
                raise ValueError("the requested ratio would require removing samples")
            return {classes[minority_index]: generated}

        raise TypeError("sampling_strategy must be a supported string, dict, or float")

    def fit_resample(self, X, y, *, sample_weight=None):
        """Validate inputs, generate synthetic rows, and return resampled data."""
        if not isinstance(self.k_neighbors, Integral) or isinstance(
            self.k_neighbors, (bool, np.bool_)
        ):
            raise TypeError("k_neighbors must be an integer")
        if int(self.k_neighbors) < 1:
            raise ValueError("k_neighbors must be at least 1")

        X, y = validate_data(
            self,
            X,
            y,
            reset=True,
            accept_sparse=False,
            dtype=FLOAT_DTYPES,
            ensure_all_finite=True,
        )
        check_classification_targets(y)
        strategy = self._resolve_sampling_strategy(y)
        self.sampling_strategy_ = strategy
        self.classes_ = np.unique(y)

        if sample_weight is None:
            checked_weight = None
        else:
            checked_weight = _check_sample_weight(
                sample_weight,
                X,
                dtype=float,
                ensure_non_negative=True,
            )

        X_parts = [X.copy()]
        y_parts = [y.copy()]
        parent_rows = []
        lambdas = []
        generated_weights = []

        for class_label, number_to_generate in strategy.items():
            if number_to_generate == 0:
                continue
            class_indices = np.flatnonzero(np.equal(y, class_label))
            if len(class_indices) <= int(self.k_neighbors):
                raise ValueError(
                    "each sampled class needs more rows than k_neighbors"
                )
            X_class = X[class_indices]
            neighbors = NearestNeighbors(n_neighbors=int(self.k_neighbors) + 1)
            neighbors.fit(X_class)
            neighbor_table = neighbors.kneighbors(
                X_class, return_distance=False
            )[:, 1:]

            random_state = check_random_state(self.random_state)
            choices = random_state.randint(
                low=0,
                high=neighbor_table.size,
                size=int(number_to_generate),
            )
            steps = random_state.uniform(size=int(number_to_generate))
            local_parents = np.floor_divide(choices, neighbor_table.shape[1])
            neighbor_columns = np.mod(choices, neighbor_table.shape[1])
            local_neighbors = neighbor_table[local_parents, neighbor_columns]
            differences = X_class[local_neighbors] - X_class[local_parents]
            X_new = X_class[local_parents] + steps[:, np.newaxis] * differences
            X_new = X_new.astype(X.dtype, copy=False)
            y_new = np.full(int(number_to_generate), class_label, dtype=y.dtype)
            X_parts.append(X_new)
            y_parts.append(y_new)

            global_parents = class_indices[local_parents]
            global_neighbors = class_indices[local_neighbors]
            parent_rows.extend(
                zip(global_parents.tolist(), global_neighbors.tolist(), strict=True)
            )
            lambdas.extend(steps.tolist())
            if checked_weight is not None:
                generated_weights.extend(
                    (
                        (1.0 - step) * checked_weight[parent]
                        + step * checked_weight[neighbor]
                    )
                    for parent, neighbor, step in zip(
                        global_parents, global_neighbors, steps, strict=True
                    )
                )

        X_resampled = np.vstack(X_parts)
        y_resampled = np.hstack(y_parts)
        self.parent_indices_ = np.asarray(parent_rows, dtype=np.intp).reshape(-1, 2)
        self.lambdas_ = np.asarray(lambdas, dtype=float)
        if checked_weight is None:
            self.sample_weight_resampled_ = None
        else:
            self.sample_weight_resampled_ = np.concatenate(
                [checked_weight, np.asarray(generated_weights, dtype=float)]
            )
        return X_resampled, y_resampled
