from __future__ import annotations

from collections.abc import Mapping

import pytest
from tests.fakes import FakeEmbeddingClient, FakeOntology, FakeTitleTaxonomy

from resume_ranker.models.common import StageResult
from resume_ranker.models.config import ScoringConfig
from resume_ranker.models.jobspec import JobSpec, ResponsibilityChunk
from resume_ranker.models.llm import LLMResult
from resume_ranker.models.resume import (
    Bullet,
    CanonicalResume,
    DatePrecision,
    DateValue,
    ExperienceEntry,
)
from resume_ranker.models.run import ScoringContext
from resume_ranker.protocols import LLMClient
from resume_ranker.scoring.dimensions.s3_semantic import S3Semantic, SemanticRubricOutput


class FakeRubricLLM(LLMClient):
    """Deterministic LLM client that returns fixed R-SEM rubric scores."""

    def __init__(self, scores: tuple[float, ...] = (80.0, 90.0)) -> None:
        self.scores = scores

    async def structured(
        self,
        *,
        template: str,
        variables: Mapping[str, object],
        schema: type[object],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[object]]:
        chosen = self.scores[:samples]
        return StageResult(
            value=LLMResult(samples=tuple(SemanticRubricOutput(score=score) for score in chosen))
        )


@pytest.fixture
def rubric_llm() -> FakeRubricLLM:
    return FakeRubricLLM(scores=(80.0, 90.0))


@pytest.fixture
def embedding_client() -> FakeEmbeddingClient:
    return FakeEmbeddingClient()


@pytest.fixture
def scoring_config() -> ScoringConfig:
    return ScoringConfig()


@pytest.fixture
def scoring_context(
    embedding_client: FakeEmbeddingClient, scoring_config: ScoringConfig
) -> ScoringContext:
    return ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=embedding_client,
        llm=None,
        config=scoring_config,
        now="2026-08-29",
    )


@pytest.fixture
def s3() -> S3Semantic:
    return S3Semantic()


@pytest.fixture
def resume() -> CanonicalResume:
    text = "Built PySpark pipelines with Python and Spark."
    return CanonicalResume(
        candidate_id="c_test",
        summary={"text": "Senior data engineer with Python and Spark."},
        experience=(
            ExperienceEntry(
                employer="Acme",
                title_raw="Senior Data Engineer",
                start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                end=DateValue(value=None, precision=DatePrecision.PRESENT),
                bullets=(
                    Bullet(text=text, span=(0, len(text))),
                    Bullet(
                        text="Deployed Kafka streaming pipelines.",
                        span=(
                            len(text) + 1,
                            len(text) + 1 + len("Deployed Kafka streaming pipelines."),
                        ),
                    ),
                ),
            ),
        ),
    )


@pytest.fixture
def spec() -> JobSpec:
    return JobSpec(
        job_id="jd_test",
        title="Senior Data Engineer",
        responsibility_chunks=(
            ResponsibilityChunk(
                id="rc1", text="Build data pipelines with Python and Spark.", weight=5
            ),
            ResponsibilityChunk(id="rc2", text="Stream processing with Kafka.", weight=3),
            ResponsibilityChunk(id="rc3", text="Infrastructure as code with Terraform.", weight=2),
        ),
    )


@pytest.fixture
def large_pool(resume: CanonicalResume) -> tuple[CanonicalResume, ...]:
    """A pool of 30 identical resumes for calibration tests."""
    return tuple(
        CanonicalResume(
            candidate_id=f"c_pool_{i:03d}",
            experience=resume.experience,
            summary=resume.summary,
        )
        for i in range(30)
    )
