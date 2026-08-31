from __future__ import annotations

import asyncio
import concurrent.futures
from collections.abc import Coroutine, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, TypeVar, cast

import numpy as np
from pydantic import BaseModel, Field

from resume_ranker.embeddings.classifier import KnnClassifier
from resume_ranker.models.embeddings import Vector
from resume_ranker.models.jobspec import JobSpec, PreferredSkill, RequiredSkill
from resume_ranker.models.resume import Bullet, CanonicalResume
from resume_ranker.models.run import ScoringContext
from resume_ranker.models.scoring import Evidence, PoolStatistics, SubScore
from resume_ranker.protocols import EmbeddingClient
from resume_ranker.scoring.registry import dimension

T = TypeVar("T")


class SemanticRubricOutput(BaseModel):
    """Structured output expected from the R-SEM LLM rubric (TRD §6.1)."""

    score: float = Field(..., ge=0.0, le=100.0)
    rationale: str = ""
    spans: list[tuple[int, int]] = Field(default_factory=list)


@dataclass(frozen=True)
class _Chunk:
    """A piece of text used for semantic comparison."""

    text: str
    source: str
    weight: int = 1
    span: tuple[int, int] | None = None
    origin_id: str = ""


@dimension
class S3Semantic:
    """Semantic relevance dimension (TRD §5.3.3)."""

    id: ClassVar[str] = "S3"
    name: ClassVar[str] = "Semantic relevance"
    requires: ClassVar[frozenset[str]] = frozenset({"embeddings"})

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.3 — Semantic relevance."""
        if ctx.embeddings is None:
            return SubScore(
                dimension=self.id,
                value=None,
                notes=("S3_EMBEDDING_UNAVAILABLE",),
            )

        client = cast(EmbeddingClient, ctx.embeddings)

        jd_chunks = sorted(_jd_chunks(spec), key=lambda chunk: chunk.text)
        if not jd_chunks:
            return SubScore(
                dimension=self.id,
                value=None,
                notes=("S3_NO_JD_CHUNKS",),
            )

        resume_chunks = sorted(_resume_chunks(resume), key=lambda chunk: chunk.text)
        if not resume_chunks:
            raw = 0.0
            calibrated = _calibrate(raw, ctx.pool)
            value = 100.0 * calibrated
            return SubScore(
                dimension=self.id,
                value=value,
                evidence=(),
                detail={
                    "raw": raw,
                    "calibrated": calibrated,
                    "pool_size": ctx.pool.size,
                    "anchors": (ctx.pool.anchor_low, ctx.pool.anchor_high),
                    "rubric_mean": None,
                    "rubric_stdev": 0.0,
                },
            )

        # Use cached JD vectors from pool if available
        if ctx.pool.jd_vectors is not None:
            jd_vectors = [tuple(v) for v in ctx.pool.jd_vectors]
        else:
            jd_vectors = list(_run(client.embed([chunk.text for chunk in jd_chunks])))
        resume_vectors = list(_run(client.embed([chunk.text for chunk in resume_chunks])))

        raw = _raw_similarity(jd_chunks, resume_chunks, jd_vectors, resume_vectors)
        calibrated = _calibrate(raw, ctx.pool)

        # LLM rubric removed; S3 is computed entirely from local embeddings.
        value = 100.0 * calibrated
        value = max(0.0, min(100.0, value))

        evidence = _evidence_from_best_match(jd_chunks, jd_vectors, resume_chunks, resume_vectors)

        detail: dict[str, Any] = {
            "raw": raw,
            "calibrated": calibrated,
            "pool_size": ctx.pool.size,
            "p10": ctx.pool.p10,
            "p90": ctx.pool.p90,
            "anchors": (ctx.pool.anchor_low, ctx.pool.anchor_high),
            "rubric_mean": None,
            "rubric_stdev": 0.0,
            "chunk_counts": {"jd": len(jd_chunks), "resume": len(resume_chunks)},
            "mode": "offline",
        }

        return SubScore(dimension=self.id, value=value, evidence=evidence, detail=detail)

    def prepare(
        self,
        resumes: Sequence[CanonicalResume],
        spec: JobSpec,
        ctx: ScoringContext,
    ) -> PoolStatistics:
        """TRD §5.3.3 — Compute pool-wide calibration anchors for S3.

        This two-pass design lets the pipeline embed the pool once and reuse the
        percentile anchors when scoring each candidate.
        """
        if ctx.embeddings is None:
            return PoolStatistics(size=len(resumes), anchor_low=0.25, anchor_high=0.70)

        client = cast(EmbeddingClient, ctx.embeddings)

        jd_chunks = sorted(_jd_chunks(spec), key=lambda chunk: chunk.text)
        if not jd_chunks:
            return PoolStatistics(size=len(resumes), anchor_low=0.25, anchor_high=0.70)

        jd_vectors = _run(client.embed([chunk.text for chunk in jd_chunks]))
        # Store JD vectors as list of lists for JSON serialization
        jd_vectors_list = [list(v) for v in jd_vectors]
        raw_values: list[float] = []
        for resume in resumes:
            resume_chunks = sorted(_resume_chunks(resume), key=lambda chunk: chunk.text)
            if resume_chunks:
                resume_vectors = _run(client.embed([chunk.text for chunk in resume_chunks]))
                raw = _raw_similarity(jd_chunks, resume_chunks, jd_vectors, resume_vectors)
            else:
                raw = 0.0
            raw_values.append(raw)

        n = len(raw_values)
        if n >= ctx.config.semantic.pool_calibration_min_size:
            arr = np.asarray(raw_values, dtype=np.float64)
            p10 = float(np.percentile(arr, 10))
            p90 = float(np.percentile(arr, 90))
            return PoolStatistics(
                size=n,
                p10=p10,
                p90=p90,
                anchor_low=0.25,
                anchor_high=0.70,
                jd_vectors=jd_vectors_list,
            )

        return PoolStatistics(size=n, anchor_low=0.25, anchor_high=0.70, jd_vectors=jd_vectors_list)


def _run(coro: Coroutine[Any, Any, T]) -> T:  # noqa: UP047
    """Run an async coroutine from a synchronous scoring call.

    Always executes in a fresh thread with a new event loop to avoid
    conflicts with any running loop in the calling thread.
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(asyncio.run, coro).result()


def _resume_chunks(resume: CanonicalResume) -> list[_Chunk]:
    """TRD §5.3.3 — Resume chunks: one per bullet/project/summary paragraph."""
    chunks: list[_Chunk] = []

    def _from_bullets(bullets: tuple[Bullet, ...], origin_id: str) -> None:
        for bullet in bullets:
            chunks.append(
                _Chunk(
                    text=bullet.text,
                    source="resume",
                    weight=1,
                    span=bullet.span,
                    origin_id=origin_id,
                )
            )

    for idx, entry in enumerate(resume.experience):
        _from_bullets(entry.bullets, f"experience:{idx}")
    for idx, project in enumerate(resume.projects):
        _from_bullets(project.bullets, f"project:{idx}")
    for key, value in resume.summary.items():
        if isinstance(value, str):
            chunks.append(
                _Chunk(
                    text=value,
                    source="resume",
                    weight=1,
                    span=None,
                    origin_id=f"summary:{key}",
                )
            )
    return chunks


def _jd_chunks(spec: JobSpec) -> list[_Chunk]:
    """TRD §5.3.3 — JD requirement chunks (responsibilities + requirements)."""
    chunks: list[_Chunk] = []
    for rc in spec.responsibility_chunks:
        chunks.append(
            _Chunk(
                text=rc.text,
                source="jobspec",
                weight=rc.weight,
                origin_id=rc.id,
            )
        )
    for required_skill in spec.required_skills:
        chunks.append(_from_skill(required_skill, "required"))
    for preferred_skill in spec.preferred_skills:
        chunks.append(_from_skill(preferred_skill, "preferred"))
    return chunks


def _from_skill(skill: RequiredSkill | PreferredSkill, route: str) -> _Chunk:
    return _Chunk(
        text=skill.canonical,
        source="jobspec",
        weight=skill.weight,
        origin_id=f"{route}:{skill.canonical}",
    )


def _raw_similarity(
    jd_chunks: Sequence[_Chunk],
    resume_chunks: Sequence[_Chunk],
    jd_vectors: Sequence[Vector],
    resume_vectors: Sequence[Vector],
) -> float:
    """TRD §5.3.3 — classifier-based asymmetric similarity, JD-weighted mean.

    Instead of a raw cosine matrix, a K-nearest-neighbour classifier is fit on
    the resume chunks and each JD chunk is classified against them.  The maximum
    predicted probability for a JD chunk is used as its relevance score.
    """
    if not jd_chunks or not resume_chunks or not jd_vectors or not resume_vectors:
        return 0.0
    resume_features = np.asarray(resume_vectors, dtype=np.float64)
    resume_labels = list(range(len(resume_chunks)))
    classifier = KnnClassifier(
        resume_features,
        resume_labels,
        n_neighbors=5,
        weights="distance",
        metric="cosine",
    )
    jd_features = np.asarray(jd_vectors, dtype=np.float64)
    proba = classifier.predict_proba(jd_features)
    max_proba = np.max(proba, axis=1)
    weights = np.asarray([chunk.weight for chunk in jd_chunks], dtype=np.float64)
    total = np.sum(weights)
    if total <= 0.0:
        return 0.0
    return float(np.sum(weights * max_proba) / total)


def _calibrate(raw: float, pool: PoolStatistics) -> float:
    """TRD §5.3.3 — pool calibration with fixed anchors below the minimum size."""
    if pool.size >= 30 and pool.p10 is not None and pool.p90 is not None:
        p10 = pool.p10
        p90 = pool.p90
    else:
        p10 = pool.anchor_low
        p90 = pool.anchor_high
    denominator = max(p90 - p10, 0.05)
    calibrated = (raw - p10) / denominator
    return max(0.0, min(1.0, calibrated))


def _llm_rubric_score(
    _jd_chunks: Sequence[_Chunk],
    _resume_chunks: Sequence[_Chunk],
    _ctx: ScoringContext,
) -> tuple[float | None, float]:
    """R-SEM LLM rubric is disabled; only local embeddings are used for S3."""
    return None, 0.0


def _evidence_from_best_match(
    jd_chunks: Sequence[_Chunk],
    jd_vectors: Sequence[Vector],
    resume_chunks: Sequence[_Chunk],
    resume_vectors: Sequence[Vector],
) -> tuple[Evidence, ...]:
    """Return the highest-similarity resume chunk with a verified span.

    A scikit-learn nearest-neighbour index fit on the resume chunks is used to
    rank all (JD chunk, resume chunk) pairs by cosine distance.  The first pair
    whose resume chunk has a verified span is returned as evidence.
    """
    if not jd_chunks or not resume_chunks or not jd_vectors or not resume_vectors:
        return ()
    resume_features = np.asarray(resume_vectors, dtype=np.float64)
    resume_labels = list(range(len(resume_chunks)))
    classifier = KnnClassifier(
        resume_features,
        resume_labels,
        n_neighbors=1,
        weights="uniform",
        metric="cosine",
    )
    jd_features = np.asarray(jd_vectors, dtype=np.float64)
    distances, indices = classifier.nearest_neighbors(jd_features, n_neighbors=len(resume_chunks))
    if distances.shape[1] == 0:
        return ()

    # Collect every (jd_idx, resume_idx) pair with its distance, then pick the
    # closest pair whose resume chunk carries a verified span.
    pairs = [
        (float(distances[jd_idx, rank]), jd_idx, int(indices[jd_idx, rank]))
        for jd_idx in range(len(jd_chunks))
        for rank in range(indices.shape[1])
    ]
    pairs.sort()
    for _, _jd_idx, resume_idx in pairs:
        chunk = resume_chunks[resume_idx]
        if chunk.span is not None:
            return (Evidence(span=chunk.span, quote=chunk.text, source="resume"),)
    return ()
