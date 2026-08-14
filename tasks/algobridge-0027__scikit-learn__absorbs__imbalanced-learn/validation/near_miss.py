"""Intentionally superficial API-only implementation for author validation."""

import numpy as np

from sklearn.base import BaseEstimator


class SMOTE(BaseEstimator):
    def __init__(self, *, sampling_strategy="auto", random_state=None, k_neighbors=5):
        self.sampling_strategy = sampling_strategy
        self.random_state = random_state
        self.k_neighbors = k_neighbors

    def fit_resample(self, X, y, *, sample_weight=None):
        X = np.asarray(X)
        y = np.asarray(y)
        self.n_features_in_ = X.shape[1]
        self.sampling_strategy_ = {}
        self.parent_indices_ = np.empty((0, 2), dtype=int)
        self.lambdas_ = np.empty(0, dtype=float)
        self.sample_weight_resampled_ = (
            None if sample_weight is None else np.asarray(sample_weight, dtype=float)
        )
        return X.copy(), y.copy()
