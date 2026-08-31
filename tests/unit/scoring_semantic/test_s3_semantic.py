from __future__ import annotations

import random
from copy import deepcopy
from typing import Any

import pytest
from tests.fakes import FakeEmbeddingClient

from resume_ranker.models.config import ScoringConfig
from resume_ranker.models.jobspec import JobSpec, ResponsibilityChunk
from resume_ranker.models.resume import CanonicalResume
from resume_ranker.models.run import ScoringContext
from resume_ranker.models.scoring import SubScore
from resume_ranker.scoring.dimensions.s3_semantic import S3Semantic


def test_s3_returns_subscore_offline(
    s3: S3Semantic,
    resume: CanonicalResume,
    spec: JobSpec,
    scoring_context: ScoringContext,
) -> None:
    score = s3.score(resume, spec, scoring_context)
    assert isinstance(score, SubScore)
    assert score.dimension == "S3"
    assert score.value is not None
    assert 0.0 <= score.value <= 100.0
    assert score.detail["mode"] == "offline"
    assert score.detail["rubric_mean"] is None
    assert score.evidence
    all_bullet_text = {bullet.text for entry in resume.experience for bullet in entry.bullets}
    for ev in score.evidence:
        assert ev.source == "resume"
        assert ev.quote in all_bullet_text


def test_s3_no_embeddings(
    s3: S3Semantic, resume: CanonicalResume, spec: JobSpec, scoring_config: ScoringConfig
) -> None:
    ctx = ScoringContext(
        ontology=None,  # type: ignore[arg-type]
        titles=None,  # type: ignore[arg-type]
        embeddings=None,
        llm=None,
        config=scoring_config,
        now="2026-08-29",
    )
    score = s3.score(resume, spec, ctx)
    assert score.value is None
    assert "S3_EMBEDDING_UNAVAILABLE" in score.notes


def test_s3_no_jd_chunks(
    s3: S3Semantic, resume: CanonicalResume, scoring_context: ScoringContext
) -> None:
    spec = JobSpec(job_id="jd_empty", title="Empty")
    score = s3.score(resume, spec, scoring_context)
    assert score.value is None
    assert "S3_NO_JD_CHUNKS" in score.notes


def test_s3_hybrid_formula(
    s3: S3Semantic,
    resume: CanonicalResume,
    spec: JobSpec,
    embedding_client: FakeEmbeddingClient,
    scoring_config: ScoringConfig,
    rubric_llm: Any,
) -> None:
    ctx = ScoringContext(
        ontology=None,  # type: ignore[arg-type]
        titles=None,  # type: ignore[arg-type]
        embeddings=embedding_client,
        llm=rubric_llm,
        config=scoring_config,
        now="2026-08-29",
    )
    score = s3.score(resume, spec, ctx)
    assert score.value is not None
    assert score.detail["rubric_mean"] == 85.0
    assert score.detail["rubric_stdev"] == pytest.approx(7.071, abs=0.001)
    expected = 0.6 * (100.0 * score.detail["calibrated"]) + 0.4 * 85.0
    assert score.value == pytest.approx(expected, abs=0.001)
    assert score.detail["mode"] == "hybrid"


def test_s3_llm_degrade(
    s3: S3Semantic,
    resume: CanonicalResume,
    spec: JobSpec,
    embedding_client: FakeEmbeddingClient,
    scoring_config: ScoringConfig,
) -> None:
    from resume_ranker.models.common import StageResult

    class FailingLLM:
        async def structured(self, **kwargs: object) -> StageResult:
            return StageResult(value=None)

    ctx = ScoringContext(
        ontology=None,  # type: ignore[arg-type]
        titles=None,  # type: ignore[arg-type]
        embeddings=embedding_client,
        llm=FailingLLM(),  # type: ignore[arg-type]
        config=scoring_config,
        now="2026-08-29",
    )
    score = s3.score(resume, spec, ctx)
    assert score.value is not None
    assert score.detail["rubric_mean"] is None


def test_s3_requires_embeddings(s3: S3Semantic) -> None:
    assert s3.requires == frozenset({"embeddings"})


def test_s3_no_resume_chunks(
    s3: S3Semantic, spec: JobSpec, scoring_context: ScoringContext
) -> None:
    empty_resume = CanonicalResume(candidate_id="c_empty")
    score = s3.score(empty_resume, spec, scoring_context)
    assert score.value == pytest.approx(0.0, abs=0.001)
    assert score.detail["raw"] == pytest.approx(0.0, abs=0.001)
    assert score.detail["calibrated"] == 0.0


def test_s3_chunk_order_independence(
    s3: S3Semantic,
    resume: CanonicalResume,
    spec: JobSpec,
    scoring_context: ScoringContext,
) -> None:
    score_a = s3.score(resume, spec, scoring_context)
    shuffled = deepcopy(resume)
    experience = shuffled.experience[0]
    bullets = list(experience.bullets)
    random.shuffle(bullets)
    experience.bullets = tuple(bullets)
    score_b = s3.score(shuffled, spec, scoring_context)
    assert score_a.value == pytest.approx(score_b.value, abs=0.001)
    assert score_a.detail["raw"] == pytest.approx(score_b.detail["raw"], abs=0.001)


def test_s3_pool_calibration_small_anchors(
    s3: S3Semantic,
    resume: CanonicalResume,
    spec: JobSpec,
    scoring_context: ScoringContext,
) -> None:
    score = s3.score(resume, spec, scoring_context)
    assert score.detail["pool_size"] == 0
    assert score.detail["p10"] is None
    assert score.detail["p90"] is None
    # With an empty pool the anchors are used.
    assert score.detail["anchors"] == (0.25, 0.70)


def test_s3_pool_calibration_large(
    s3: S3Semantic,
    resume: CanonicalResume,
    spec: JobSpec,
    scoring_context: ScoringContext,
) -> None:
    empty = CanonicalResume(candidate_id="c_empty")
    mixed = tuple([empty] * 15 + [resume] * 15)
    pool = s3.prepare(mixed, spec, scoring_context)
    assert pool.size == 30
    assert pool.p10 is not None
    assert pool.p90 is not None
    assert pool.p10 < pool.p90

    ctx_with_pool = ScoringContext(
        ontology=scoring_context.ontology,
        titles=scoring_context.titles,
        embeddings=scoring_context.embeddings,
        llm=None,
        config=scoring_context.config,
        now="2026-08-29",
        pool=pool,
    )
    score = s3.score(resume, spec, ctx_with_pool)
    assert score.detail["pool_size"] == 30
    assert score.detail["p10"] == pool.p10
    assert score.detail["p90"] == pool.p90


def test_s3_weighted_jd_chunks(
    s3: S3Semantic, resume: CanonicalResume, scoring_context: ScoringContext
) -> None:
    spec = JobSpec(
        job_id="jd_weighted",
        title="Role",
        responsibility_chunks=(
            ResponsibilityChunk(
                id="match", text="Build data pipelines with Python and Spark.", weight=5
            ),
            ResponsibilityChunk(id="gap", text="Terraform infrastructure.", weight=1),
        ),
    )
    score = s3.score(resume, spec, scoring_context)
    assert score.value is not None
    assert 0.0 < score.detail["raw"] < 1.0


def test_s3_prepare_with_no_embeddings(
    s3: S3Semantic, resume: CanonicalResume, spec: JobSpec, scoring_config: ScoringConfig
) -> None:
    ctx = ScoringContext(
        ontology=None,  # type: ignore[arg-type]
        titles=None,  # type: ignore[arg-type]
        embeddings=None,
        llm=None,
        config=scoring_config,
        now="2026-08-29",
    )
    pool = s3.prepare((resume,), spec, ctx)
    assert pool.size == 1
    assert pool.p10 is None
    assert pool.p90 is None
