from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import TYPE_CHECKING, cast

import numpy as np
from rapidfuzz import fuzz

from resume_ranker.embeddings.classifier import KnnClassifier
from resume_ranker.models.config import OntologyConfig
from resume_ranker.models.ontology import SkillMatch, SkillRelation
from resume_ranker.ontology.loader import SkillEntry, load_skills

if TYPE_CHECKING:
    from resume_ranker.protocols import EmbeddingClient


_PUNCT_RE = re.compile(r"[^\w\s]+")


def _normalise(raw: str) -> str:
    """Lower-case and strip whitespace."""
    return raw.strip().lower()


def _strip_punctuation(raw: str) -> str:
    """Lower-case, remove punctuation and collapse whitespace."""
    collapsed = _PUNCT_RE.sub(" ", raw.strip().lower())
    return " ".join(collapsed.split())


class SkillOntology:
    """Curated skill graph implementing the OntologyIndex protocol (TRD §3.5).

    The match cascade follows FR-501: exact, alias, case/punctuation-insensitive,
    fuzzy ratio, and finally embedding cosine. The embedding tier is only used
    when a compatible client is supplied; otherwise it is skipped, which is the
    deterministic/offline mode.
    """

    version: str

    def __init__(
        self,
        data_path: str | Path | None = None,
        embeddings: EmbeddingClient | None = None,
        config: OntologyConfig | None = None,
    ) -> None:
        """Load the ontology from ``data_path``.

        Args:
            data_path: Directory containing ``skills.json``. Defaults to the bundled
                versioned data directory relative to this module.
            embeddings: Optional embedding client for the embedding match tier. The
                ontology never imports ``resume_ranker.embeddings`` directly; it only
                holds a reference passed in by the caller.
            config: Threshold configuration; defaults to ``OntologyConfig``.
        """
        resolved_path = Path(data_path) if data_path is not None else self._default_path()
        cfg = config if config is not None else OntologyConfig()
        self._fuzzy_threshold = cfg.fuzzy_min_ratio
        self._embedding_threshold = cfg.embedding_min_cosine

        entries, alias_map, self.version = load_skills(resolved_path)
        self._entries = entries
        self._alias_map = alias_map
        self._canonical_set = frozenset(e.canonical for e in entries)
        self._canonicals = tuple(e.canonical for e in entries)
        self._timeless = frozenset(e.canonical for e in entries if e.timeless)
        self._children = {e.canonical: e.children for e in entries}
        self._parents = {e.canonical: e.parents for e in entries}
        self._embedding_client = embeddings
        self._embedding_vectors: dict[str, np.ndarray] | None = None
        self._embedding_classifier: KnnClassifier[str] | None = None

    @staticmethod
    def _default_path() -> Path:
        """Return the default data directory shipped with the component."""
        return Path(__file__).resolve().parents[3] / "data" / "ontology" / "2026.07"

    def canonicalise(self, raw: str) -> SkillMatch | None:
        """Map a raw skill string to a canonical ontology entry.

        Implements the FR-501 cascade. ``SkillMatch.relation`` records which
        tier produced the match.
        """
        normalised = _normalise(raw)
        if not normalised:
            return None

        # Exact match.
        if normalised in self._canonical_set:
            return SkillMatch(canonical=normalised, raw=raw, relation=SkillRelation.EXACT)

        # Curated alias match.
        if normalised in self._alias_map:
            return SkillMatch(
                canonical=self._alias_map[normalised],
                raw=raw,
                relation=SkillRelation.ALIAS,
            )

        # Case/punctuation-insensitive match.
        stripped = _strip_punctuation(raw)
        if stripped in self._canonical_set:
            return SkillMatch(canonical=stripped, raw=raw, relation=SkillRelation.EXACT)
        if stripped in self._alias_map:
            return SkillMatch(
                canonical=self._alias_map[stripped],
                raw=raw,
                relation=SkillRelation.ALIAS,
            )

        # Fuzzy match is computed against the lower-cased, whitespace-normalised
        # raw string so that punctuation differences (e.g. missing hyphen) are
        # preserved as signals rather than stripped away.
        fuzzy_match = self._best_fuzzy_match(normalised)
        if fuzzy_match is not None:
            return SkillMatch(canonical=fuzzy_match, raw=raw, relation=SkillRelation.FUZZY)

        # Embedding match.
        embedding_match = self._embedding_match(raw)
        if embedding_match is not None:
            return embedding_match

        # Unmapped: caller must retain the raw string as free-text (FR-506).
        return None

    def relation(self, candidate: str, target: str) -> SkillRelation:
        """Return the relationship between two canonical skill strings."""
        c = candidate.strip().lower()
        t = target.strip().lower()
        if c == t:
            return SkillRelation.EXACT
        if self._alias_map.get(c) == t or self._alias_map.get(t) == c:
            return SkillRelation.ALIAS
        if t in self._parents.get(c, ()):
            return SkillRelation.CHILD
        if t in self._children.get(c, ()):
            return SkillRelation.PARENT
        if self._fuzzy_match_between(c, t):
            return SkillRelation.FUZZY
        return SkillRelation.NONE

    def is_timeless(self, canonical: str) -> bool:
        """Return whether a canonical skill is exempt from recency decay."""
        return canonical.strip().lower() in self._timeless

    def _best_fuzzy_match(self, query: str) -> str | None:
        """Return the best fuzzy-matched canonical above the threshold, if any."""
        if not self._canonicals:
            return None
        best_canonical: str | None = None
        best_score = 0.0
        for canonical in self._canonicals:
            score = fuzz.ratio(query, canonical)
            if score > best_score:
                best_score = score
                best_canonical = canonical
        if best_canonical is not None and best_score >= self._fuzzy_threshold:
            return best_canonical
        return None

    def _fuzzy_match_between(self, a: str, b: str) -> bool:
        """Return True if the fuzzy ratio between two strings meets the threshold."""
        return bool(fuzz.ratio(a, b) >= self._fuzzy_threshold)

    def _embedding_match(self, raw: str) -> SkillMatch | None:
        """Try the embedding classifier tier when a client is available.

        The nearest-neighbour lookup is replaced by a scikit-learn
        ``KNeighborsClassifier`` trained on the canonical-skill embeddings.
        The classifier predicts the closest canonical label, and a separate
        ``NearestNeighbors`` index provides the cosine distance to the nearest
        training example for thresholding.
        """
        if self._embedding_client is None:
            return None
        try:
            classifier = self._ensure_embedding_classifier()
        except RuntimeError:
            return None
        if classifier is None:
            return None
        raw_vector = self._embed_sync([raw])
        if not raw_vector:
            return None
        query = np.asarray([raw_vector[0]], dtype=np.float64)
        predicted = classifier.predict(query)[0]
        distance = classifier.nearest_distances(query)[0]
        # KNN classifier with cosine distance: distance == 1 - cosine_similarity.
        cosine_similarity = 1.0 - float(distance)
        if cosine_similarity >= self._embedding_threshold:
            return SkillMatch(canonical=predicted, raw=raw, relation=SkillRelation.EMBEDDING)
        return None

    def _ensure_embedding_vectors(self) -> dict[str, np.ndarray]:
        """Lazy, one-time build of the canonical-skill embedding index and classifier."""
        if self._embedding_vectors is not None:
            return self._embedding_vectors
        self._embedding_vectors = {}
        if self._embedding_client is None:
            return self._embedding_vectors
        vectors = self._embed_sync(list(self._canonicals))
        for canonical, vector in zip(self._canonicals, vectors, strict=True):
            self._embedding_vectors[canonical] = np.asarray(vector, dtype=np.float64)
        # Build classifier once alongside vectors
        if self._embedding_vectors and self._embedding_classifier is None:
            labels = list(self._embedding_vectors.keys())
            features = np.asarray(
                [self._embedding_vectors[label] for label in labels], dtype=np.float64
            )
            self._embedding_classifier = KnnClassifier(
                features,
                labels,
                n_neighbors=5,
                weights="distance",
                metric="cosine",
            )
        return self._embedding_vectors

    def _ensure_embedding_classifier(self) -> KnnClassifier[str] | None:
        """Return the cached KNN classifier, building vectors first if needed."""
        self._ensure_embedding_vectors()  # ensures both vectors and classifier are built
        return self._embedding_classifier

    def _embed_sync(self, texts: list[str]) -> list[tuple[float, ...]]:
        """Run the async embedding client synchronously when safe."""
        if self._embedding_client is None:
            return []
        try:
            return cast(list[tuple[float, ...]], asyncio.run(self._embedding_client.embed(texts)))
        except RuntimeError:
            # Called inside an already-running event loop; skip the embedding tier.
            return []

    @staticmethod
    def _nearest(query: tuple[float, ...], vectors: dict[str, np.ndarray]) -> tuple[str, float]:
        """Return the canonical with the highest cosine similarity to ``query``."""
        query_array = np.asarray(query, dtype=np.float32)
        best_canonical = ""
        best_score = -1.0
        for canonical, vector in vectors.items():
            score = _cosine(query_array, vector)
            if score > best_score:
                best_score = score
                best_canonical = canonical
        return best_canonical, best_score


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors (TRD §5.3.1 embedding tier)."""
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    if norm == 0:
        return 0.0
    return float(np.dot(a, b) / norm)


def _entry_to_dict(entry: SkillEntry) -> dict[str, object]:
    """Serialise a SkillEntry for debugging; kept in the same module for cohesion."""
    return {
        "canonical": entry.canonical,
        "aliases": entry.aliases,
        "parents": entry.parents,
        "children": entry.children,
        "timeless": entry.timeless,
    }
