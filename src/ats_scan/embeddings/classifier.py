from __future__ import annotations

from collections.abc import Sequence
from typing import cast

import numpy as np
from sklearn.cluster import KMeans  # type: ignore[import-untyped]
from sklearn.neighbors import (  # type: ignore[import-untyped]
    KNeighborsClassifier,
    NearestNeighbors,
)


class KnnClassifier[T]:
    """K-nearest-neighbour classifier over embedding vectors.

    The classifier wraps scikit-learn's ``KNeighborsClassifier`` and a parallel
    ``NearestNeighbors`` index so callers can get both the predicted label and the
    distance to the nearest neighbour of that label.
    """

    def __init__(
        self,
        features: np.ndarray,
        labels: Sequence[T],
        *,
        n_neighbors: int = 5,
        weights: str = "distance",
        metric: str = "cosine",
    ) -> None:
        self._raw_labels: list[T] = list(labels)
        self._label_set: list[T] = sorted(set(self._raw_labels), key=str)
        self._label_to_index: dict[T, int] = {label: i for i, label in enumerate(self._label_set)}
        self._y = np.array(
            [self._label_to_index[label] for label in self._raw_labels], dtype=np.int64
        )
        effective_neighbors = min(n_neighbors, len(features))
        self._clf = KNeighborsClassifier(
            n_neighbors=effective_neighbors,
            weights=weights,
            metric=metric,
            n_jobs=1,
        )
        self._clf.fit(features, self._y)
        self._nn = NearestNeighbors(n_neighbors=1, metric=metric, n_jobs=1)
        self._nn.fit(features)

    def predict(self, features: np.ndarray) -> list[T]:
        """Return the predicted label for each row in ``features``."""
        indices = cast(np.ndarray, self._clf.predict(features))
        return [self._label_set[int(i)] for i in indices]

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        """Return the probability distribution over labels for each row."""
        return cast(np.ndarray, self._clf.predict_proba(features))

    def nearest_distances(self, features: np.ndarray) -> np.ndarray:
        """Return the cosine distance to the single nearest training vector."""
        distances, _ = cast(tuple[np.ndarray, np.ndarray], self._nn.kneighbors(features))
        return distances[:, 0]

    def nearest_neighbors(
        self, features: np.ndarray, n_neighbors: int
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return distances and indices of the ``n_neighbors`` closest vectors."""
        effective = min(n_neighbors, len(self._raw_labels))
        if effective <= 0:
            empty = np.zeros((len(features), 0))
            return empty, empty
        distances, indices = cast(
            tuple[np.ndarray, np.ndarray],
            self._nn.kneighbors(features, n_neighbors=effective),
        )
        return distances, indices


class KMeansClusterer:
    """Lightweight scikit-learn KMeans wrapper for clustering embedding vectors."""

    def __init__(self, n_clusters: int, *, random_state: int = 0) -> None:
        self._n_clusters = n_clusters
        self._random_state = random_state
        self._model: KMeans | None = None
        self._labels: np.ndarray = np.array([], dtype=np.int64)

    def fit(self, features: np.ndarray) -> KMeansClusterer:
        """Fit KMeans on ``features`` and store cluster labels."""
        n_clusters = min(self._n_clusters, max(1, len(features)))
        if n_clusters <= 1:
            self._model = None
            self._labels = np.zeros(len(features), dtype=np.int64)
            return self
        self._model = KMeans(
            n_clusters=n_clusters,
            random_state=self._random_state,
            n_init="auto",
            max_iter=300,
        )
        self._labels = cast(np.ndarray, self._model.fit_predict(features))
        return self

    def predict(self, features: np.ndarray) -> np.ndarray:
        """Assign new rows to the learned clusters."""
        if self._model is None:
            return np.zeros(len(features), dtype=np.int64)
        return cast(np.ndarray, self._model.predict(features))

    def center_distance(self, features: np.ndarray) -> np.ndarray:
        """Return the distance from each row to its nearest cluster centre."""
        if self._model is None:
            return np.zeros(len(features))
        return cast(np.ndarray, self._model.transform(features)).min(axis=1)

    def labels(self) -> np.ndarray:
        """Return the cluster labels of the training data."""
        return self._labels
