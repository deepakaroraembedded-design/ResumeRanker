from __future__ import annotations

import pytest
from tests.fakes import FakeEmbeddingClient, FakeOntology, FakeTitleTaxonomy

from resume_ranker.models.config import ScoringConfig
from resume_ranker.models.jobspec import JobSpec, PreferredSkill, RequiredSkill
from resume_ranker.models.resume import (
    Bullet,
    CanonicalResume,
    DatePrecision,
    DateValue,
    ExperienceEntry,
    SkillMention,
)
from resume_ranker.models.run import ScoringContext
from resume_ranker.models.scoring import SubScore
from resume_ranker.scoring.dimensions.s1_required_skills import S1RequiredSkills
from resume_ranker.scoring.dimensions.s2_preferred_skills import S2PreferredSkills
from resume_ranker.scoring.dimensions.s3_semantic import S3Semantic
from resume_ranker.scoring.dimensions.s4_experience import S4Experience
from resume_ranker.scoring.dimensions.s5_title import S5Title
from resume_ranker.scoring.dimensions.s6_domain import S6Domain
from resume_ranker.scoring.dimensions.s7_education import S7Education
from resume_ranker.scoring.dimensions.s8_skill_recency import S8SkillRecency
from resume_ranker.scoring.dimensions.s9_trajectory import S9Trajectory
from resume_ranker.scoring.dimensions.s10_parseability import S10Parseability


@pytest.fixture
def minimal_resume() -> CanonicalResume:
    return CanonicalResume(
        candidate_id="c_test",
        experience=(
            ExperienceEntry(
                employer="Acme",
                title_raw="Senior Data Engineer",
                start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                end=DateValue(value=None, precision=DatePrecision.PRESENT),
                bullets=(Bullet(text="Built PySpark pipelines", span=(0, 28)),),
                skills_evidenced=("python", "apache-spark"),
            ),
        ),
        skills=(
            SkillMention(raw="Python", canonical="python", last_used="2026-08"),
            SkillMention(raw="Spark", canonical="apache-spark", last_used="2026-08"),
        ),
    )


@pytest.fixture
def minimal_spec() -> JobSpec:
    return JobSpec(
        job_id="jd_test",
        title="Senior Data Engineer",
        required_skills=(
            RequiredSkill(canonical="python", weight=5),
            RequiredSkill(canonical="apache-spark", weight=5),
            RequiredSkill(canonical="dbt", weight=2),
        ),
        preferred_skills=(
            PreferredSkill(canonical="kafka", weight=3),
            PreferredSkill(canonical="terraform", weight=2),
        ),
    )


@pytest.fixture
def scoring_context() -> ScoringContext:
    return ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=None,
        config=ScoringConfig(),
        now="2026-08-29",
    )


def test_s1_required_skills(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.1 — required skills coverage with deterministic fakes."""
    score = S1RequiredSkills().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)
    assert score.value == pytest.approx(80.0, abs=0.1)


def test_s2_preferred_skills(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.2 — preferred skills coverage."""
    score = S2PreferredSkills().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)
    assert score.value == pytest.approx(0.0, abs=0.1)


def test_s3_semantic(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.3 — semantic relevance."""
    score = S3Semantic().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)


def test_s4_experience(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.4 — relevant experience depth."""
    score = S4Experience().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)


def test_s5_title(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.5 — role and title alignment."""
    score = S5Title().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)


def test_s6_domain(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.6 — domain and industry match."""
    score = S6Domain().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)


def test_s7_education(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.7 — education and certifications."""
    score = S7Education().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)


def test_s8_skill_recency(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.8 — skill recency."""
    score = S8SkillRecency().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)
    assert score.value == pytest.approx(66.7, abs=0.1)


def test_s9_trajectory(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.9 — career trajectory and stability."""
    score = S9Trajectory().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)


def test_s10_parseability(
    minimal_resume: CanonicalResume, minimal_spec: JobSpec, scoring_context: ScoringContext
) -> None:
    """TRD §5.3.10 — resume parseability."""
    score = S10Parseability().score(minimal_resume, minimal_spec, scoring_context)
    assert isinstance(score, SubScore)
