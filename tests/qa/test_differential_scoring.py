from __future__ import annotations

import asyncio
import math
from datetime import date
from typing import Any

import pytest
from tests.fakes import FakeEmbeddingClient, FakeOntology, FakeTitleTaxonomy
from tests.qa.strategies import skill_case

from ats_scan.models.common import IntegrityFinding, StageResult
from ats_scan.models.config import IntegrityConfig, OverqualificationConfig, ScoringConfig
from ats_scan.models.jobspec import (
    DomainRequirement,
    EducationRequirement,
    ExperienceRequirement,
    JobSpec,
    PreferredSkill,
    RequiredSkill,
    ResponsibilityChunk,
)
from ats_scan.models.llm import LLMResult
from ats_scan.models.resume import (
    Bullet,
    CanonicalResume,
    Certification,
    DatePrecision,
    DateValue,
    EducationEntry,
    EmploymentType,
    ExperienceEntry,
    ExtractionMetadata,
    IntegritySummary,
    ProjectEntry,
    SkillMention,
    Timeline,
)
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import (
    GapDetail,
    MatchDetail,
    MatchRoute,
    PoolStatistics,
    SubScore,
)
from ats_scan.scoring.aggregate import aggregate
from ats_scan.scoring.confidence import confidence
from ats_scan.scoring.dimensions.s1_required_skills import S1RequiredSkills
from ats_scan.scoring.dimensions.s2_preferred_skills import S2PreferredSkills
from ats_scan.scoring.dimensions.s3_semantic import (
    S3Semantic,
    SemanticRubricOutput,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _calibrate as s3_calibrate,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _Chunk as S3Chunk,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _cosine_matrix as s3_cosine_matrix,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _evidence_from_best_match as s3_evidence_from_best_match,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _from_skill as s3_from_skill,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _jd_chunks as s3_jd_chunks,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _llm_rubric_score as s3_llm_rubric_score,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _raw_similarity as s3_raw_similarity,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _resume_chunks as s3_resume_chunks,
)
from ats_scan.scoring.dimensions.s3_semantic import (
    _run as s3_run,
)
from ats_scan.scoring.dimensions.s4_experience import (
    S4Experience,
)
from ats_scan.scoring.dimensions.s4_experience import (
    _build_intervals as s4_build_intervals,
)
from ats_scan.scoring.dimensions.s4_experience import (
    _domain_similarity as s4_domain_similarity,
)
from ats_scan.scoring.dimensions.s4_experience import (
    _Interval as S4Interval,
)
from ats_scan.scoring.dimensions.s4_experience import (
    _raw_years as s4_raw_years,
)
from ats_scan.scoring.dimensions.s4_experience import (
    _relevant_years as s4_relevant_years,
)
from ats_scan.scoring.dimensions.s4_experience import _resolve_date as s4_resolve_date
from ats_scan.scoring.dimensions.s4_experience import (
    _s4_from_years as s4_from_years,
)
from ats_scan.scoring.dimensions.s4_experience import (
    _skill_overlap as s4_skill_overlap,
)
from ats_scan.scoring.dimensions.s4_experience import (
    _title_similarity as s4_title_similarity,
)
from ats_scan.scoring.dimensions.s5_title import (
    S5Title,
)
from ats_scan.scoring.dimensions.s5_title import (
    _recency_weight as s5_recency_weight,
)
from ats_scan.scoring.dimensions.s5_title import _resolve_date as s5_resolve_date
from ats_scan.scoring.dimensions.s5_title import (
    _role_alignment as s5_role_alignment,
)
from ats_scan.scoring.dimensions.s6_domain import (
    S6Domain,
)
from ats_scan.scoring.dimensions.s6_domain import (
    _domain_match as s6_domain_match,
)
from ats_scan.scoring.dimensions.s6_domain import (
    _recency_weight as s6_recency_weight,
)
from ats_scan.scoring.dimensions.s6_domain import _resolve_date as s6_resolve_date
from ats_scan.scoring.dimensions.s7_education import (
    S7Education,
)
from ats_scan.scoring.dimensions.s7_education import (
    _cert_name as s7_cert_name,
)
from ats_scan.scoring.dimensions.s7_education import (
    _certification_component as s7_certification_component,
)
from ats_scan.scoring.dimensions.s7_education import (
    _degree_ordinal as s7_degree_ordinal,
)
from ats_scan.scoring.dimensions.s7_education import (
    _education_component as s7_education_component,
)
from ats_scan.scoring.dimensions.s7_education import (
    _match_certification as s7_match_certification,
)
from ats_scan.scoring.dimensions.s7_education import _parse_date as s7_parse_date
from ats_scan.scoring.dimensions.s8_skill_recency import S8SkillRecency
from ats_scan.scoring.dimensions.s9_trajectory import (
    S9Trajectory,
)
from ats_scan.scoring.dimensions.s9_trajectory import _resolve_date as s9_resolve_date
from ats_scan.scoring.dimensions.s9_trajectory import (
    _role_months as s9_role_months,
)
from ats_scan.scoring.dimensions.s9_trajectory import (
    _seniority_ordinal as s9_seniority_ordinal,
)
from ats_scan.scoring.dimensions.s9_trajectory import (
    _stability_component as s9_stability_component,
)
from ats_scan.scoring.dimensions.s9_trajectory import (
    _trajectory_component as s9_trajectory_component,
)
from ats_scan.scoring.dimensions.s10_parseability import S10Parseability
from ats_scan.scoring.dimensions.s10_parseability import _is_unparseable as s10_is_unparseable
from ats_scan.scoring.evidence import (
    ProficiencyKind,
    _best_match_value,
    _evidence_from_entry,
    _evidence_from_mention,
    _proficiency_from_mention,
    _route_for,
    _to_evidence,
    collect_skill_evidence,
    f_match,
    f_recency,
    parse_iso_date,
    recency_for_skill,
    score_skill_coverage,
    years_since,
)

DIMENSIONS: dict[str, Any] = {
    "S1": S1RequiredSkills,
    "S2": S2PreferredSkills,
    "S3": S3Semantic,
    "S4": S4Experience,
    "S5": S5Title,
    "S6": S6Domain,
    "S7": S7Education,
    "S8": S8SkillRecency,
    "S9": S9Trajectory,
    "S10": S10Parseability,
}


@pytest.mark.slow
@pytest.mark.parametrize("dim", list(DIMENSIONS))
def test_dimension_agrees_with_oracle(dim: str) -> None:
    """Differential oracle check for a single scoring dimension."""
    cls = DIMENSIONS[dim]
    resume, spec, ctx, oracle_inputs = skill_case()

    try:
        sub = cls().score(resume, spec, ctx)
    except NotImplementedError:
        pytest.skip(f"{dim} implementation is not available yet")

    if dim not in oracle_inputs:
        pytest.skip(f"oracle case for {dim} is not yet defined")

    expected = oracle_inputs[dim]
    assert sub.value == pytest.approx(expected, abs=1e-6), dim


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2023", date(2023, 1, 1)),
        ("2023-05", date(2023, 5, 1)),
        ("2023-05-15", date(2023, 5, 15)),
        ("", None),
        (None, None),
        ("not-a-date", None),
        ("2023-13-45", None),
    ],
)
def test_resolve_date_across_dimensions(raw: str | None, expected: date | None) -> None:
    """Date resolution is exercised by every dimension that reads role dates."""
    now = date(2026, 8, 29)
    value = DateValue(value=raw, precision=DatePrecision.UNKNOWN) if raw is not None else None
    for func in (s4_resolve_date, s5_resolve_date, s6_resolve_date, s9_resolve_date):
        assert func(value, now) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2023", date(2023, 1, 1)),
        ("2023-05", date(2023, 5, 1)),
        ("2023-05-15", date(2023, 5, 15)),
        ("", None),
        ("not-a-date", None),
        ("2023-13-45", None),
    ],
)
def test_s7_parse_date(raw: str, expected: date | None) -> None:
    """S7 certification expiry parsing must cover all common formats."""
    assert s7_parse_date(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2023-05-15", date(2023, 5, 15)),
        ("2023-05", date(2023, 5, 1)),
        ("2023", date(2023, 1, 1)),
        ("", None),
        (None, None),
        ("not-a-date", None),
    ],
)
def test_parse_iso_date_variants(raw: str | None, expected: date | None) -> None:
    """Evidence date parsing is on the hot path for S1, S2 and S8."""
    assert parse_iso_date(raw) == expected


@pytest.mark.parametrize(
    ("last", "expected"),
    [
        (date(2026, 8, 29), 0.0),
        (date(2026, 7, 29), 1 / 12.0),
        (date(2025, 8, 29), 1.0),
        (date(2027, 8, 29), 0.0),
    ],
)
def test_years_since_variants(last: date, expected: float) -> None:
    """Skill-recency time-to-event conversion is a frequent mutation target."""
    now = date(2026, 8, 29)
    assert years_since(last, now) == pytest.approx(expected, abs=1e-6)


def _context() -> ScoringContext:
    return ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=None,
        config=ScoringConfig(),
        now="2026-08-29",
    )


class _DeterministicLLM:
    """Fake LLM client that always returns two identical rubric samples."""

    async def structured(
        self,
        *,
        template: str,
        variables: dict[str, object],
        schema: type[Any],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[Any]]:
        sample = SemanticRubricOutput(score=80.0, rationale="ok", spans=[(0, 5)])
        return StageResult(value=LLMResult(samples=(sample,) * samples))


def _full_resume() -> CanonicalResume:
    return CanonicalResume(
        candidate_id="c_full",
        extraction=ExtractionMetadata(method="tesseract", columns_detected=2),
        parse_completeness=0.8,
        skills=(
            SkillMention(
                raw="Python",
                canonical="python",
                last_used="2026-08",
                first_used="2020-01",
                sections=("skills", "experience"),
                mentions=2,
                evidence_spans=((0, 6),),
            ),
            SkillMention(
                raw="Spark",
                canonical="apache-spark",
                last_used="2026-08",
                first_used="2021-03",
                sections=("skills", "experience"),
                mentions=1,
                evidence_spans=((0, 5),),
            ),
            SkillMention(
                raw="Kafka",
                canonical="kafka",
                last_used="2023-01",
                first_used="2019-01",
                sections=("skills", "projects"),
                mentions=1,
                evidence_spans=((0, 5),),
            ),
        ),
        experience=(
            ExperienceEntry(
                title_raw="Software Engineer",
                title_canonical="software engineer",
                title_family="software engineer",
                seniority="senior",
                employment_type=EmploymentType.FULL_TIME,
                start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                bullets=(Bullet(text="Developed Python and Spark pipelines", span=(0, 35)),),
                skills_evidenced=("python", "apache-spark"),
            ),
            ExperienceEntry(
                title_raw="Intern",
                title_canonical="software engineer",
                title_family="software engineer",
                seniority="intern",
                employment_type=EmploymentType.INTERNSHIP,
                start=DateValue(value="2019-06", precision=DatePrecision.MONTH),
                end=DateValue(value="2019-12", precision=DatePrecision.MONTH),
                bullets=(),
                skills_evidenced=(),
            ),
            ExperienceEntry(
                title_raw="Data Scientist",
                title_canonical="data scientist",
                title_family="data science",
                seniority="senior",
                employment_type=EmploymentType.FULL_TIME,
                start=DateValue(value="2018-01", precision=DatePrecision.MONTH),
                end=DateValue(value="2019-12", precision=DatePrecision.MONTH),
                bullets=(),
                skills_evidenced=("statistics",),
            ),
        ),
        education=(
            EducationEntry(
                degree_level="bachelor",
                field="computer science",
                start=DateValue(value="2012-09", precision=DatePrecision.MONTH),
                end=DateValue(value="2016-06", precision=DatePrecision.MONTH),
            ),
        ),
        certifications=(
            Certification(
                name="AWS",
                canonical="aws-certified",
                issued="2020-05",
                expires="2027-12",
                status="active",
            ),
        ),
        projects=(
            ProjectEntry(
                title="Open Source Tool",
                bullets=(Bullet(text="Built a Kafka consumer", span=(0, 20)),),
                skills_evidenced=("kafka",),
            ),
        ),
        summary={"headline": "Experienced engineer", "objective": "Build data systems"},
        integrity=IntegritySummary(),
    )


def _full_spec() -> JobSpec:
    return JobSpec(
        job_id="jd_full",
        title="Senior Software Engineer",
        title_family="software engineer",
        domain=DomainRequirement(industry="software engineering", required=True),
        experience=ExperienceRequirement(min_years=5, target_years=8, count_internships=False),
        education=EducationRequirement(
            min_level="bachelor",
            fields=("computer science",),
            equivalent_experience_allowed=True,
        ),
        required_skills=(
            RequiredSkill(canonical="python", weight=5),
            RequiredSkill(canonical="apache-spark", weight=5),
            RequiredSkill(canonical="kafka", weight=3),
        ),
        preferred_skills=(PreferredSkill(canonical="sql", weight=3),),
        responsibility_chunks=(
            ResponsibilityChunk(
                id="rc1", text="Design and build scalable data pipelines", weight=5
            ),
            ResponsibilityChunk(id="rc2", text="Collaborate with cross-functional teams", weight=2),
        ),
        certifications=({"name": "AWS Certified", "canonical": "aws-certified", "weight": 2},),
    )


def test_full_dimension_smoke() -> None:
    """End-to-end regression on a resume that exercises every dimension."""
    resume = _full_resume()
    spec = _full_spec()
    ctx = _context()

    assert S1RequiredSkills().score(resume, spec, ctx).value == pytest.approx(80.0, abs=1e-6)
    assert S2PreferredSkills().score(resume, spec, ctx).value == pytest.approx(0.0, abs=1e-6)

    s3 = S3Semantic().score(resume, spec, ctx)
    assert s3.value == pytest.approx(0.0, abs=1e-6)
    assert s3.detail is not None
    assert s3.detail["chunk_counts"] == {"jd": 6, "resume": 4}
    assert s3.detail["raw"] == pytest.approx(0.11165547966089587, abs=1e-6)

    assert S4Experience().score(resume, spec, ctx).value == pytest.approx(43.62, abs=1e-2)
    assert S5Title().score(resume, spec, ctx).value == pytest.approx(14.87, abs=1e-2)
    assert S6Domain().score(resume, spec, ctx).value == pytest.approx(59.47, abs=1e-2)
    assert S7Education().score(resume, spec, ctx).value == pytest.approx(100.0, abs=1e-6)
    assert S8SkillRecency().score(resume, spec, ctx).value == pytest.approx(100.0, abs=1e-6)
    assert S9Trajectory().score(resume, spec, ctx).value == pytest.approx(72.5, abs=1e-2)
    assert S10Parseability().score(resume, spec, ctx).value == pytest.approx(45.0, abs=1e-6)


# --- S3 semantic helpers ----------------------------------------------------


def test_s3_resume_chunks() -> None:
    """Resume chunk extraction must include bullets, project bullets and summary text."""
    resume = _full_resume()
    chunks = s3_resume_chunks(resume)
    texts = {c.text for c in chunks}
    assert len(chunks) == 4
    assert "Developed Python and Spark pipelines" in texts
    assert "Built a Kafka consumer" in texts
    assert "Experienced engineer" in texts
    assert "Build data systems" in texts
    for chunk in chunks:
        assert chunk.source == "resume"
        assert chunk.weight == 1
        assert chunk.origin_id


def test_s3_jd_chunks() -> None:
    """JD chunk extraction must include responsibility chunks and skill requirements."""
    spec = _full_spec()
    chunks = s3_jd_chunks(spec)
    texts = {c.text for c in chunks}
    assert len(chunks) == 6
    assert "Design and build scalable data pipelines" in texts
    assert "Collaborate with cross-functional teams" in texts
    for skill in ("python", "apache-spark", "kafka", "sql"):
        assert skill in texts
    for chunk in chunks:
        assert chunk.source == "jobspec"
        assert chunk.weight >= 1
        assert chunk.origin_id


def test_s3_from_skill() -> None:
    """Skill-to-chunk conversion preserves canonical text and weight."""
    chunk = s3_from_skill(RequiredSkill(canonical="python", weight=5), "required")
    assert chunk.text == "python"
    assert chunk.weight == 5
    assert chunk.origin_id == "required:python"


def test_s3_cosine_matrix() -> None:
    """Pairwise cosine matrix must be normalised and handle empty/edge inputs."""
    assert s3_cosine_matrix([], []).shape == (0, 0)
    assert s3_cosine_matrix([(1.0, 0.0)], []).shape == (0, 0)

    a = [(1.0, 0.0, 0.0)]
    b = [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    matrix = s3_cosine_matrix(a, b)
    assert matrix.shape == (1, 2)
    assert matrix[0, 0] == pytest.approx(1.0, abs=1e-6)
    assert matrix[0, 1] == pytest.approx(0.0, abs=1e-6)

    # Zero vectors produce NaN in cosine; the function must replace them with 0.
    zero_matrix = s3_cosine_matrix([(0.0, 0.0, 0.0)], [(1.0, 0.0, 0.0)])
    assert zero_matrix[0, 0] == pytest.approx(0.0, abs=1e-6)


def test_s3_raw_similarity() -> None:
    """Asymmetric JD-weighted similarity must be positive for a clear match."""
    jd_chunk = s3_from_skill(RequiredSkill(canonical="python", weight=5), "required")
    resume_chunk = S3Chunk(text="Python", source="resume", weight=1, span=(0, 6), origin_id="r1")
    client = FakeEmbeddingClient()
    raw = s3_raw_similarity(
        [jd_chunk],
        [resume_chunk],
        [client._vector("python")],
        [client._vector("Python")],
    )
    assert raw > 0.0

    # Empty inputs must return 0.0 without crashing.
    assert s3_raw_similarity([], [], [], []) == pytest.approx(0.0, abs=1e-6)


def test_s3_calibrate() -> None:
    """Calibration must map the anchor range to [0, 1] and clamp outside it."""
    pool = PoolStatistics(size=0, anchor_low=0.25, anchor_high=0.70)
    assert s3_calibrate(0.0, pool) == pytest.approx(0.0, abs=1e-6)
    assert s3_calibrate(0.475, pool) == pytest.approx(0.5, abs=1e-6)
    assert s3_calibrate(1.0, pool) == pytest.approx(1.0, abs=1e-6)

    # Pool calibration branch with explicit percentiles.
    pool_with_stats = PoolStatistics(size=30, p10=0.20, p90=0.80)
    assert s3_calibrate(0.50, pool_with_stats) == pytest.approx(0.5, abs=1e-6)


def test_s3_evidence_from_best_match() -> None:
    """Best-match evidence must return the span of the most similar resume chunk."""
    jd_chunk = s3_from_skill(RequiredSkill(canonical="python", weight=5), "required")
    resume_chunk = S3Chunk(
        text="Python development",
        source="resume",
        weight=1,
        span=(0, 18),
        origin_id="r1",
    )
    client = FakeEmbeddingClient()
    evidence = s3_evidence_from_best_match(
        [jd_chunk],
        [client._vector("python")],
        [resume_chunk],
        [client._vector("Python development")],
    )
    assert len(evidence) == 1
    assert evidence[0].span == (0, 18)


def test_s3_llm_rubric_score() -> None:
    """The LLM rubric helper must aggregate structured samples deterministically."""
    jd_chunk = s3_from_skill(RequiredSkill(canonical="python", weight=5), "required")
    resume_chunk = S3Chunk(text="Python", source="resume", weight=1, span=(0, 6), origin_id="r1")
    ctx = ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=_DeterministicLLM(),
        config=ScoringConfig(),
        now="2026-08-29",
    )
    mean, stdev = s3_llm_rubric_score([jd_chunk], [resume_chunk], ctx)
    assert mean == pytest.approx(80.0, abs=1e-6)
    assert stdev == pytest.approx(0.0, abs=1e-6)


class _EmptyLLM:
    """Fake LLM client that returns an empty sample set."""

    async def structured(
        self,
        *,
        template: str,
        variables: dict[str, object],
        schema: type[Any],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[Any]]:
        return StageResult(value=LLMResult(samples=()))


class _TwoSampleLLM:
    """Fake LLM client that returns two different rubric scores."""

    async def structured(
        self,
        *,
        template: str,
        variables: dict[str, object],
        schema: type[Any],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[Any]]:
        return StageResult(
            value=LLMResult(
                samples=(
                    SemanticRubricOutput(score=80.0, rationale="a", spans=[(0, 5)]),
                    SemanticRubricOutput(score=90.0, rationale="b", spans=[(0, 5)]),
                )
            )
        )


class _RecordingLLM:
    """Fake LLM client that records the arguments passed to it."""

    call: dict[str, object] | None = None

    async def structured(
        self,
        *,
        template: str,
        variables: dict[str, object],
        schema: type[Any],
        samples: int = 1,
        trace: str,
    ) -> StageResult[LLMResult[Any]]:
        self.call = {
            "template": template,
            "variables": variables,
            "schema": schema,
            "samples": samples,
            "trace": trace,
        }
        sample = SemanticRubricOutput(score=80.0, rationale="ok", spans=[(0, 5)])
        return StageResult(value=LLMResult(samples=(sample,) * samples))


class _BadLLM:
    """Fake LLM client that does not conform to the LLMClient protocol."""


@pytest.mark.parametrize(
    ("llm", "expected"),
    [
        (None, (None, 0.0)),
        (_BadLLM(), (None, 0.0)),
        (_EmptyLLM(), (None, 0.0)),
    ],
)
def test_s3_llm_rubric_score_guard_branches(llm: Any, expected: tuple[float | None, float]) -> None:
    """The LLM rubric helper must short-circuit cleanly on missing or bad clients."""
    ctx = ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=llm,
        config=ScoringConfig(),
        now="2026-08-29",
    )
    jd_chunk = s3_from_skill(RequiredSkill(canonical="python", weight=5), "required")
    resume_chunk = S3Chunk(text="Python", source="resume", weight=1, span=(0, 6), origin_id="r1")
    assert s3_llm_rubric_score([jd_chunk], [resume_chunk], ctx) == expected


def test_s3_llm_rubric_score_stdev() -> None:
    """Two samples with different scores must produce a non-zero standard deviation."""
    ctx = ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=_TwoSampleLLM(),
        config=ScoringConfig(),
        now="2026-08-29",
    )
    jd_chunk = s3_from_skill(RequiredSkill(canonical="python", weight=5), "required")
    resume_chunk = S3Chunk(text="Python", source="resume", weight=1, span=(0, 6), origin_id="r1")
    mean, stdev = s3_llm_rubric_score([jd_chunk], [resume_chunk], ctx)
    assert mean == pytest.approx(85.0, abs=1e-6)
    assert stdev > 0.0


def test_s3_llm_rubric_score_call_shape() -> None:
    """The LLM rubric helper must pass the expected R-SEM template and chunk data."""
    llm = _RecordingLLM()
    ctx = ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=llm,
        config=ScoringConfig(),
        now="2026-08-29",
    )
    jd_chunk = s3_from_skill(RequiredSkill(canonical="python", weight=5), "required")
    resume_chunk = S3Chunk(text="Python", source="resume", weight=1, span=(0, 6), origin_id="r1")
    s3_llm_rubric_score([jd_chunk], [resume_chunk], ctx)
    assert llm.call is not None
    assert llm.call["template"] == "R-SEM"
    assert llm.call["samples"] == 2
    assert llm.call["trace"] == "S3"
    assert llm.call["schema"] is SemanticRubricOutput
    variables = llm.call["variables"]
    assert variables is not None
    assert len(variables["job_chunks"]) == 1
    assert variables["job_chunks"][0]["text"] == "python"
    assert variables["job_chunks"][0]["weight"] == 5
    assert variables["resume_chunks"][0]["text"] == "Python"


# --- Evidence helpers -------------------------------------------------------


def test_route_for() -> None:
    """Skill matching must distinguish exact, alias and unrelated skills."""
    ontology = FakeOntology()
    assert _route_for("python", "python", ontology) == MatchRoute.EXACT
    assert _route_for("python", "py", ontology) == MatchRoute.ALIAS
    assert _route_for("python", "java", ontology) == MatchRoute.NONE
    assert _route_for("python", None, ontology) == MatchRoute.NONE


def test_proficiency_from_mention() -> None:
    """Mention section classification must drive the proficiency factor."""
    corroborated = SkillMention(
        raw="Python",
        canonical="python",
        sections=("skills", "experience"),
        mentions=1,
    )
    assert _proficiency_from_mention(corroborated) == ProficiencyKind.LISTED_CORROBORATED

    listed_only = SkillMention(
        raw="Python",
        canonical="python",
        sections=("skills",),
        mentions=1,
    )
    assert _proficiency_from_mention(listed_only) == ProficiencyKind.LISTED_ONLY

    incidental = SkillMention(
        raw="Python",
        canonical="python",
        sections=("experience",),
        mentions=0,
    )
    assert _proficiency_from_mention(incidental) == ProficiencyKind.INCIDENTAL


def test_evidence_from_mention() -> None:
    """A matching SkillMention must be converted to structured evidence."""
    skill = SkillMention(
        raw="Python",
        canonical="python",
        sections=("skills", "experience"),
        mentions=1,
        last_used="2026-08",
        evidence_spans=((0, 6),),
    )
    ev = _evidence_from_mention("python", skill, FakeOntology())
    assert ev is not None
    assert ev.route == MatchRoute.EXACT
    assert ev.kind == ProficiencyKind.LISTED_CORROBORATED
    assert ev.last_used == date(2026, 8, 1)


def test_evidence_from_entry() -> None:
    """Skills evidenced on an experience entry must use the entry's end date."""
    entry = ExperienceEntry(
        title_raw="Developer",
        bullets=(Bullet(text="Used Python", span=(0, 10)),),
        skills_evidenced=("python",),
        end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
    )
    ev = _evidence_from_entry("python", entry, "python", FakeOntology())
    assert ev is not None
    assert ev.route == MatchRoute.EXACT
    assert ev.canonical == "python"
    assert ev.quote == "Used Python"
    assert ev.span == (0, 10)
    assert ev.last_used == date(2026, 8, 1)

    # When the entry already has a span and no bullets, that span is preserved.
    entry_with_span = ExperienceEntry(
        title_raw="Developer",
        bullets=(),
        skills_evidenced=("python",),
        span=(20, 30),
    )
    ev2 = _evidence_from_entry("python", entry_with_span, "python", FakeOntology())
    assert ev2 is not None
    assert ev2.span == (20, 30)

    # Unmatched skills must return None.
    no_match = ExperienceEntry(
        title_raw="Developer",
        bullets=(),
        skills_evidenced=("java",),
    )
    assert _evidence_from_entry("python", no_match, "java", FakeOntology()) is None


def test_collect_skill_evidence() -> None:
    """Evidence collection must aggregate skills from all resume sections."""
    resume = _full_resume()
    evidence = collect_skill_evidence(resume, "python", FakeOntology())
    assert len(evidence) >= 1


def test_score_skill_coverage() -> None:
    """Weighted skill coverage on the full resume must match the S1 engine score."""
    resume = _full_resume()
    spec = _full_spec()
    ctx = _context()
    score, _, _, _ = score_skill_coverage(resume, spec.required_skills, ctx)
    assert score == pytest.approx(80.0, abs=1e-6)


def test_recency_for_skill() -> None:
    """The best recency factor for a recently used skill must be 1.0."""
    resume = _full_resume()
    ctx = _context()
    rec, _ = recency_for_skill(
        resume, "python", date(2026, 8, 29), ctx.config.recency, FakeOntology()
    )
    assert rec == pytest.approx(1.0, abs=1e-6)


def test_f_recency_and_f_match() -> None:
    """Factor tables must be deterministic and bounded."""
    assert f_recency(0.0, 4.0, 0.5) == pytest.approx(1.0, abs=1e-6)
    assert f_recency(100.0, 4.0, 0.5) == pytest.approx(0.5, abs=1e-6)
    assert f_match(MatchRoute.EXACT) == pytest.approx(1.0, abs=1e-6)
    assert f_match(MatchRoute.CHILD) == pytest.approx(0.90, abs=1e-6)
    assert f_match(MatchRoute.NONE) == pytest.approx(0.0, abs=1e-6)


def test_best_match_value() -> None:
    """Best match must select the highest m = match * proficiency * recency."""
    now = date(2026, 8, 29)
    ctx = _context()
    ev = _evidence_from_mention(
        "python",
        SkillMention(
            raw="Python",
            canonical="python",
            sections=("skills", "experience"),
            mentions=1,
            last_used="2026-08",
            evidence_spans=((0, 6),),
        ),
        FakeOntology(),
    )
    assert ev is not None
    best, chosen = _best_match_value((ev,), now, ctx.config, FakeOntology())
    assert best > 0.0
    assert chosen is not None
    assert chosen.canonical == "python"


def test_score_skill_coverage_gaps() -> None:
    """A skill with no evidence must produce a gap and a zero score contribution."""
    resume = _full_resume()
    ctx = _context()
    missing = (RequiredSkill(canonical="missing", weight=5),)
    score, evidence, matches, gaps = score_skill_coverage(resume, missing, ctx)
    assert score == pytest.approx(0.0, abs=1e-6)
    assert len(gaps) == 1
    assert len(matches) == 0


def test_score_skill_coverage_match_details() -> None:
    """Matched skills must produce match details with the expected criterion."""
    resume = _full_resume()
    ctx = _context()
    python_only = (RequiredSkill(canonical="python", weight=5),)
    score, evidence, matches, gaps = score_skill_coverage(resume, python_only, ctx)
    assert score > 0.0
    assert len(matches) == 1
    assert matches[0].criterion == "python"
    assert len(gaps) == 0


def test_recency_for_skill_no_evidence() -> None:
    """A skill with no evidence must return zero and no evidence record."""
    resume = _full_resume()
    ctx = _context()
    rec, ev = recency_for_skill(
        resume, "missing", date(2026, 8, 29), ctx.config.recency, FakeOntology()
    )
    assert rec == pytest.approx(0.0, abs=1e-6)
    assert ev is None


# --- S7 education helpers ---------------------------------------------------


def test_s7_education_component() -> None:
    """Education component must score matched, adjacent and unmatched levels."""
    resume = _full_resume()
    spec = _full_spec()
    ctx = _context()
    assert s7_education_component(resume, spec, ctx) == pytest.approx(1.0, abs=1e-6)

    # No requirement should be neutral.
    spec_no_edu = spec.model_copy(update={"education": None})
    assert s7_education_component(resume, spec_no_edu, ctx) == pytest.approx(1.0, abs=1e-6)


@pytest.mark.parametrize(
    ("candidate_cert", "expected_factor"),
    [
        (Certification(name="AWS", canonical="aws-certified"), 1.0),
        (Certification(name="AWS", canonical="aws-certified", expires="2020-05"), 0.40),
        (Certification(name="AWS", canonical="aws-certified", status="in-progress"), 0.50),
    ],
)
def test_s7_match_certification(candidate_cert: Certification, expected_factor: float) -> None:
    """Certification matching must respect expiry and in-progress status."""
    now = date(2026, 8, 29)
    factor = s7_match_certification("aws-certified", (candidate_cert,), now)
    assert factor == pytest.approx(expected_factor, abs=1e-6)


def test_s7_certification_component() -> None:
    """Certification component must aggregate weighted matches."""
    resume = _full_resume()
    spec = _full_spec()
    now = date(2026, 8, 29)
    assert s7_certification_component(resume, spec, now) == pytest.approx(1.0, abs=1e-6)


# --- S4 experience helpers ------------------------------------------------


def test_s4_from_years() -> None:
    """S4 piecewise mapping must cover all branches from zero to overqualified."""
    from ats_scan.models.config import OverqualificationConfig

    no_overqual = OverqualificationConfig(enabled=False)
    assert s4_from_years(0.0, 5, 8, no_overqual) == pytest.approx(0.0, abs=1e-6)
    assert s4_from_years(2.5, 5, 8, no_overqual) == pytest.approx(40.0, abs=1e-6)
    assert s4_from_years(5.0, 5, 8, no_overqual) == pytest.approx(70.0, abs=1e-6)
    assert s4_from_years(8.0, 5, 8, no_overqual) == pytest.approx(100.0, abs=1e-6)
    assert s4_from_years(10.0, 5, 8, no_overqual) == pytest.approx(100.0, abs=1e-6)

    with_overqual = OverqualificationConfig(enabled=True, cap=10, points_per_year=3)
    assert s4_from_years(10.0, 5, 8, with_overqual) < 100.0


def test_s4_build_intervals_and_relevance() -> None:
    """S4 interval building must collapse roles and weight by relevance."""
    resume = _full_resume()
    spec = _full_spec()
    ctx = _context()
    intervals = s4_build_intervals(
        resume, spec, ctx, FakeTitleTaxonomy(), date(2026, 8, 29), spec.experience
    )
    assert len(intervals) > 0
    assert s4_relevant_years(intervals) > 0.0
    assert s4_raw_years(intervals) > 0.0


# --- S9 trajectory helpers --------------------------------------------------


def test_s9_seniority_ordinal() -> None:
    """Seniority mapping must distinguish junior, senior and unknown titles."""
    assert (
        s9_seniority_ordinal(ExperienceEntry(title_raw="Junior Engineer", seniority="junior")) == 1
    )
    assert (
        s9_seniority_ordinal(ExperienceEntry(title_raw="Senior Engineer", seniority="senior")) == 3
    )
    assert s9_seniority_ordinal(ExperienceEntry(title_raw="Unknown", seniority=None)) == 2


def test_s9_role_months() -> None:
    """Role-months must be positive for a normal start/end pair."""
    role = ExperienceEntry(
        start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
        end=DateValue(value="2020-06", precision=DatePrecision.MONTH),
    )
    months = s9_role_months(role, date(2026, 8, 29))
    assert months == pytest.approx(5, abs=1e-6)


def test_s9_trajectory_and_stability() -> None:
    """Trajectory and stability components must be deterministic for the full resume."""
    resume = _full_resume()
    now = date(2026, 8, 29)
    assert s9_trajectory_component(resume, now) > 0.0
    assert s9_stability_component(resume, now) > 0.0


def test_s9_trajectory_component_directions() -> None:
    """Trajectory must classify increasing, flat and decreasing seniority."""
    now = date(2026, 8, 29)
    base = _full_resume()
    increasing = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    title_raw="Junior Engineer",
                    seniority="junior",
                    start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                    end=DateValue(value="2022-01", precision=DatePrecision.MONTH),
                ),
                ExperienceEntry(
                    title_raw="Senior Engineer",
                    seniority="senior",
                    start=DateValue(value="2022-02", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_trajectory_component(increasing, now) == pytest.approx(1.00, abs=1e-6)

    decreasing = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    title_raw="Senior Engineer",
                    seniority="senior",
                    start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                    end=DateValue(value="2022-01", precision=DatePrecision.MONTH),
                ),
                ExperienceEntry(
                    title_raw="Junior Engineer",
                    seniority="junior",
                    start=DateValue(value="2022-02", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_trajectory_component(decreasing, now) == pytest.approx(0.40, abs=1e-6)

    single = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    title_raw="Engineer",
                    seniority="senior",
                    start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_trajectory_component(single, now) == pytest.approx(0.70, abs=1e-6)


def test_s9_stability_component_branches() -> None:
    """Stability must reward long tenures and skip contract roles."""
    now = date(2026, 8, 29)
    base = _full_resume()
    long_tenure = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
                ExperienceEntry(
                    start=DateValue(value="2018-01", precision=DatePrecision.MONTH),
                    end=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_stability_component(long_tenure, now) == pytest.approx(1.00, abs=1e-6)

    contract_only = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    employment_type=EmploymentType.CONTRACT,
                    start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                    end=DateValue(value="2021-01", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_stability_component(contract_only, now) == pytest.approx(0.45, abs=1e-6)


def test_s9_role_months_invalid() -> None:
    """Role-months must return None for missing or inverted dates."""
    now = date(2026, 8, 29)
    missing = ExperienceEntry()
    assert s9_role_months(missing, now) is None
    inverted = ExperienceEntry(
        start=DateValue(value="2026-08", precision=DatePrecision.MONTH),
        end=DateValue(value="2020-01", precision=DatePrecision.MONTH),
    )
    assert s9_role_months(inverted, now) is None


def test_s9_seniority_ordinal_tokens() -> None:
    """Seniority ordinal must fall back to tokens in the title."""
    assert s9_seniority_ordinal(ExperienceEntry(title_raw="Junior Engineer")) == 1
    assert s9_seniority_ordinal(ExperienceEntry(title_raw="Senior Engineer")) == 3
    assert s9_seniority_ordinal(ExperienceEntry(title_raw="Staff Engineer")) == 4
    assert s9_seniority_ordinal(ExperienceEntry(title_raw="Principal Engineer")) == 5
    assert s9_seniority_ordinal(ExperienceEntry(title_raw="Engineer")) == 2


# --- Additional evidence helpers --------------------------------------------


def test_evidence_route_for_and_proficiency() -> None:
    """Route mapping and proficiency classification must cover all branches."""
    ontology = FakeOntology()
    assert _route_for("python", "python", ontology) == MatchRoute.EXACT
    assert _route_for("python", "py", ontology) == MatchRoute.ALIAS
    assert _route_for("python", "java", ontology) == MatchRoute.NONE
    assert _route_for("python", None, ontology) == MatchRoute.NONE

    skill_experience_skills = SkillMention(
        raw="Python", sections=("experience", "skills"), mentions=2
    )
    assert _proficiency_from_mention(skill_experience_skills) == ProficiencyKind.LISTED_CORROBORATED

    skill_experience_only = SkillMention(raw="Python", sections=("experience",), mentions=2)
    assert _proficiency_from_mention(skill_experience_only) == ProficiencyKind.LISTED_CORROBORATED

    skill_experience_no_mentions = SkillMention(raw="Python", sections=("experience",), mentions=0)
    assert _proficiency_from_mention(skill_experience_no_mentions) == ProficiencyKind.INCIDENTAL

    skill_skills_only = SkillMention(raw="Python", sections=("skills",))
    assert _proficiency_from_mention(skill_skills_only) == ProficiencyKind.LISTED_ONLY


def test_evidence_from_mention_branches() -> None:
    """Evidence from mention must canonicalise raw text and reject non-matches."""
    ontology = FakeOntology()
    exact = SkillMention(
        raw="Python", canonical="python", sections=("skills",), last_used="2026-08"
    )
    ev_exact = _evidence_from_mention("python", exact, ontology)
    assert ev_exact is not None
    assert ev_exact.route == MatchRoute.EXACT

    raw_alias = SkillMention(raw="py", sections=("skills",), last_used="2026-08")
    ev_alias = _evidence_from_mention("python", raw_alias, ontology)
    assert ev_alias is not None
    assert ev_alias.route == MatchRoute.EXACT

    no_match = SkillMention(raw="Java", canonical="java", sections=("skills",), last_used="2026-08")
    assert _evidence_from_mention("python", no_match, ontology) is None

    no_evidence_span = SkillMention(
        raw="Python", canonical="python", sections=("skills",), last_used="2026-08"
    )
    ev_span = _evidence_from_mention("python", no_evidence_span, ontology)
    assert ev_span is not None
    assert ev_span.span == (0, 6)


def test_evidence_from_entry_branches() -> None:
    """Evidence from experience/project entries must use bullets and dates."""
    ontology = FakeOntology()
    entry = ExperienceEntry(
        title_raw="Engineer",
        start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
        end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
        bullets=(Bullet(text="Built Python pipelines", span=(0, 20)),),
        skills_evidenced=("python",),
    )
    ev = _evidence_from_entry("python", entry, "python", ontology)
    assert ev is not None
    assert ev.route == MatchRoute.EXACT
    assert ev.span == (0, 20)
    assert ev.quote == "Built Python pipelines"
    assert ev.raw == "python"
    assert ev.last_used == date(2026, 8, 1)

    no_match = _evidence_from_entry("python", entry, "java", ontology)
    assert no_match is None

    entry_with_span = ExperienceEntry(
        title_raw="Engineer",
        start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
        end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
        span=(5, 10),
        bullets=(Bullet(text="Built Python pipelines", span=(0, 20)),),
        skills_evidenced=("python",),
    )
    ev_span = _evidence_from_entry("python", entry_with_span, "python", ontology)
    assert ev_span is not None
    assert ev_span.span == (5, 10)
    assert ev_span.quote == "python"
    assert ev_span.raw == "python"

    entry_no_bullet = ExperienceEntry(title_raw="Engineer", skills_evidenced=("py",), span=(5, 7))
    ev2 = _evidence_from_entry("python", entry_no_bullet, "py", ontology)
    assert ev2 is not None
    assert ev2.span == (5, 7)
    assert ev2.quote == "py"
    assert ev2.raw == "py"

    # When bullets exist but no explicit span, the bullet span/text is used.
    entry_bullet_no_span = ExperienceEntry(
        title_raw="Engineer",
        skills_evidenced=("python",),
        bullets=(Bullet(text="Python code", span=None),),
    )
    ev3 = _evidence_from_entry("python", entry_bullet_no_span, "python", ontology)
    assert ev3 is not None
    assert ev3.span == (0, 11)
    assert ev3.quote == "Python code"


def test_best_match_value_and_to_evidence() -> None:
    """Best match must pick the highest combined factor and convert to evidence."""
    ctx = _context()
    ontology = FakeOntology()
    now = date(2026, 8, 29)
    newer = SkillMention(
        raw="Python",
        canonical="python",
        sections=("skills", "experience"),
        mentions=2,
        last_used="2026-08",
    )
    older = SkillMention(
        raw="Python", canonical="python", sections=("skills",), last_used="2020-01"
    )
    evidence = (
        _evidence_from_mention("python", newer, ontology),
        _evidence_from_mention("python", older, ontology),
    )
    best_m, best_ev = _best_match_value(evidence, now, ctx.config, ontology)
    assert best_m > 0.0
    assert best_ev is not None
    assert best_ev.kind == ProficiencyKind.LISTED_CORROBORATED
    assert _to_evidence(best_ev)[0].quote == "Python"
    assert _to_evidence(None) == ()


def test_score_skill_coverage_branches() -> None:
    """Skill coverage must compute weighted score, gaps and evidence."""
    ctx = _context()
    resume = _full_resume()
    matched = (
        RequiredSkill(canonical="python", weight=5),
        RequiredSkill(canonical="apache-spark", weight=5),
    )
    score, evidence, matches, gaps = score_skill_coverage(resume, matched, ctx)
    assert score > 0.0
    assert len(matches) == 2
    assert len(gaps) == 0
    assert evidence

    unmatched = (RequiredSkill(canonical="tensorflow", weight=3),)
    score0, ev0, m0, gaps0 = score_skill_coverage(resume, unmatched, ctx)
    assert score0 == pytest.approx(0.0, abs=1e-6)
    assert len(gaps0) == 1


def test_recency_for_skill_timeless_vs_old() -> None:
    """Recency for skill must use timeless half-life for timeless skills."""
    ctx = _context()
    now = date(2026, 8, 29)
    rec, ev = recency_for_skill(_full_resume(), "python", now, ctx.config.recency, ctx.ontology)
    assert rec > 0.0
    assert ev is not None

    old_project_resume = _full_resume().model_copy(
        update={
            "projects": (
                ProjectEntry(
                    title="Old tool",
                    bullets=(Bullet(text="Used Kafka", span=(0, 9)),),
                    skills_evidenced=("kafka",),
                    end=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    rec_old, ev_old = recency_for_skill(
        old_project_resume, "kafka", now, ctx.config.recency, ctx.ontology
    )
    assert rec_old < rec
    assert ev_old is not None


def test_f_match_and_f_recency() -> None:
    """Match and recency factors must cover all branches."""
    assert f_match(MatchRoute.EXACT) == pytest.approx(1.0, abs=1e-6)
    assert f_match(MatchRoute.CHILD) == pytest.approx(0.90, abs=1e-6)
    assert f_match(MatchRoute.PARENT) == pytest.approx(0.70, abs=1e-6)
    assert f_match(MatchRoute.FUZZY) == pytest.approx(0.85, abs=1e-6)
    assert f_match(MatchRoute.TRANSFERABLE) == pytest.approx(0.50, abs=1e-6)
    assert f_match(MatchRoute.NONE) == pytest.approx(0.0, abs=1e-6)
    assert f_match(MatchRoute.EMBEDDING, 0.90) == pytest.approx(0.66, abs=1e-6)
    assert f_match(MatchRoute.EMBEDDING) == pytest.approx(0.0, abs=1e-6)

    assert f_recency(0.0, 2.0, 0.5) == pytest.approx(1.0, abs=1e-6)
    assert f_recency(10.0, 2.0, 0.5) == pytest.approx(0.5, abs=1e-6)
    assert f_recency(0.0, 0.0, 0.5) == pytest.approx(1.0, abs=1e-6)


# --- Additional S3 semantic helpers ------------------------------------------


def test_s3_resume_and_jd_chunks() -> None:
    """Chunk builders must produce entries for all inputs and empty gracefully."""
    resume = _full_resume()
    assert any(c.source == "resume" for c in s3_resume_chunks(resume))
    assert (
        len(s3_resume_chunks(CanonicalResume(candidate_id="c_empty", parse_completeness=0.0))) == 0
    )

    spec = _full_spec()
    assert any(c.source == "jobspec" for c in s3_jd_chunks(spec))
    assert len(s3_jd_chunks(JobSpec(job_id="empty", title="Empty"))) == 0


def test_s3_raw_similarity_and_evidence_from_best_match() -> None:
    """Raw similarity must be weight-aware and evidence must pick the best chunk."""
    jd = [S3Chunk(text="a", source="jobspec", weight=2, origin_id="a")]
    resume = [S3Chunk(text="a", source="resume", weight=1, origin_id="a", span=(0, 1))]
    emb = FakeEmbeddingClient()
    v_a = emb._vector("a")
    v_b = emb._vector("b")
    assert s3_raw_similarity(jd, resume, (v_a,), (v_a,)) == pytest.approx(1.0, abs=1e-6)
    assert s3_raw_similarity(jd, resume, (v_a,), ()) == pytest.approx(0.0, abs=1e-6)
    assert s3_raw_similarity(jd, resume, (), (v_a,)) == pytest.approx(0.0, abs=1e-6)
    assert s3_raw_similarity([], resume, (v_a,), (v_a,)) == pytest.approx(0.0, abs=1e-6)

    assert s3_evidence_from_best_match(jd, (v_a,), resume, (v_a,)) != ()
    assert s3_evidence_from_best_match(jd, (v_a,), resume, (v_a,))[0].span == (0, 1)

    no_span_resume = [S3Chunk(text="a", source="resume", weight=1, origin_id="a", span=None)]
    assert s3_evidence_from_best_match(jd, (v_a,), no_span_resume, (v_b,)) == ()


def test_s3_run_in_event_loop() -> None:
    """_run must execute a coroutine when a loop is already running."""

    async def coro() -> int:
        return 42

    async def caller() -> int:
        return s3_run(coro())

    assert asyncio.run(caller()) == 42


# --- Aggregate and confidence ------------------------------------------------


def test_aggregate_branches() -> None:
    """Aggregation must weight, penalise, drop zero weights and handle no active dims."""
    cfg = ScoringConfig()
    integrity = IntegrityConfig(penalties={"DODGY": 5.0}, penalty_total_cap=10.0)
    findings = (IntegrityFinding(detector="fake", code="DODGY", message="bad"),)

    sub_scores = {
        "a": SubScore(dimension="a", value=100.0, weight=1.0, evidence=(), details=()),
        "b": SubScore(dimension="b", value=0.0, weight=1.0, evidence=(), details=()),
        "z": SubScore(dimension="z", value=None, weight=1.0, evidence=(), details=()),
    }
    weights = {"a": 1.0, "b": 1.0, "z": 0.0}
    agg = aggregate(sub_scores, weights, findings, cfg, integrity)
    assert agg.base_score == pytest.approx(50.0, abs=1e-6)
    assert agg.composite == pytest.approx(45.0, abs=1e-6)
    assert "PENALTY_APPLIED:DODGY" in agg.flags

    empty_agg = aggregate({}, {}, (), cfg, integrity)
    assert empty_agg.composite == pytest.approx(0.0, abs=1e-6)


def test_confidence_modes() -> None:
    """Confidence must differ between deterministic and hybrid modes."""
    resume = _full_resume()
    sub_scores = {
        "s1": SubScore(dimension="s1", value=80.0, weight=1.0, evidence=(), details=()),
    }
    det = confidence(resume, sub_scores, mode="deterministic")
    assert 0.0 <= det <= 1.0
    hybrid = confidence(resume, sub_scores, mode="hybrid", rubric_stdev=25.0)
    assert 0.0 <= hybrid <= 1.0
    assert hybrid < det


# --- Second wave: targeted survivors ----------------------------------------


def test_score_skill_coverage_more() -> None:
    """Skill coverage must handle mixed matches, aliases and zero weights."""
    ctx = _context()
    resume = _full_resume()

    partial = (
        RequiredSkill(canonical="python", weight=5),
        RequiredSkill(canonical="tensorflow", weight=3),
    )
    score, _, _, _ = score_skill_coverage(resume, partial, ctx)
    assert score == pytest.approx(80.0, abs=1e-6)

    alias_skill = (RequiredSkill(canonical="python", weight=5),)
    alias_resume = _full_resume().model_copy(
        update={"skills": (SkillMention(raw="py", sections=("skills",), last_used="2026-08"),)}
    )
    score_alias, _, _, _ = score_skill_coverage(alias_resume, alias_skill, ctx)
    assert score_alias > 0.0

    score_empty, _, _, gaps_empty = score_skill_coverage(resume, (), ctx)
    assert score_empty == pytest.approx(0.0, abs=1e-6)
    assert len(gaps_empty) == 0


def test_s3_llm_rubric_branches() -> None:
    """LLM rubric score must handle missing LLM, bad result and empty samples."""
    jd = s3_jd_chunks(_full_spec())
    resume = s3_resume_chunks(_full_resume())

    ctx_no_llm = _context()
    assert s3_llm_rubric_score(jd, resume, ctx_no_llm) == (None, 0.0)

    class _NotLLM:
        pass

    ctx_bad_llm = _context()
    object.__setattr__(ctx_bad_llm, "llm", _NotLLM())
    assert s3_llm_rubric_score(jd, resume, ctx_bad_llm) == (None, 0.0)

    class _EmptyLLM:
        async def structured(self, **kwargs: object) -> StageResult[LLMResult[Any]]:
            return StageResult(value=LLMResult(samples=()))

    ctx_empty = _context()
    object.__setattr__(ctx_empty, "llm", _EmptyLLM())
    assert s3_llm_rubric_score(jd, resume, ctx_empty) == (None, 0.0)


def test_s3_raw_similarity_weight_and_evidence_fallback() -> None:
    """Raw similarity must be zero for zero total weight and evidence must fall back."""
    emb = FakeEmbeddingClient()
    v_a = emb._vector("a")
    v_b = emb._vector("b")
    v_c = emb._vector("c")

    zero_weight = [S3Chunk(text="a", source="jobspec", weight=0, origin_id="a")]
    resume = [S3Chunk(text="a", source="resume", weight=1, origin_id="a", span=(0, 1))]
    assert s3_raw_similarity(zero_weight, resume, (v_a,), (v_a,)) == pytest.approx(0.0, abs=1e-6)

    weighted = [
        S3Chunk(text="a", source="jobspec", weight=1, origin_id="a"),
        S3Chunk(text="b", source="jobspec", weight=3, origin_id="b"),
    ]
    resume_weighted = [S3Chunk(text="b", source="resume", weight=1, origin_id="b", span=(0, 1))]
    # Both JD chunks are identical to the resume vector; weighted score must be 1.0.
    assert s3_raw_similarity(weighted, resume_weighted, (v_b, v_b), (v_b,)) == pytest.approx(
        1.0, abs=1e-6
    )

    jd_best = [S3Chunk(text="a", source="jobspec", weight=1, origin_id="a")]
    resume_no_span_best = [S3Chunk(text="a", source="resume", weight=1, origin_id="a", span=None)]
    resume_span_worse = [S3Chunk(text="b", source="resume", weight=1, origin_id="b", span=(0, 1))]
    # a is most similar to a (no span), b less similar; fallback picks b's span.
    evidence = s3_evidence_from_best_match(
        jd_best, (v_a,), (resume_no_span_best[0], resume_span_worse[0]), (v_a, v_c)
    )
    assert evidence[0].span == (0, 1)


def test_s5_s6_recency_weight_old_and_floor() -> None:
    """Recency weight must decay for old roles and respect the floor."""
    now = date(2026, 8, 29)
    old = ExperienceEntry(end=DateValue(value="2010-01", precision=DatePrecision.MONTH))
    assert s5_recency_weight(old, now, 2.0, 0.2) == pytest.approx(0.2, abs=1e-6)
    assert s6_recency_weight(old, now, 2.0, 0.2) == pytest.approx(0.2, abs=1e-6)


def test_s4_from_years_more_branches() -> None:
    """S4 from_years must cover the full branch set."""
    disabled = OverqualificationConfig(enabled=False)
    assert s4_from_years(4.0, 5, 8, disabled) == pytest.approx(58.0, abs=1e-6)
    assert s4_from_years(5.0, 5, 5, disabled) == pytest.approx(100.0, abs=1e-6)
    assert s4_from_years(0.0, 0, 0, disabled) == pytest.approx(70.0, abs=1e-6)

    enabled = OverqualificationConfig(enabled=True, cap=10, points_per_year=3)
    assert s4_from_years(8.0, 5, 8, enabled) == pytest.approx(100.0, abs=1e-6)
    assert s4_from_years(11.0, 5, 8, enabled) == pytest.approx(91.0, abs=1e-6)


def test_s4_build_intervals_count_internships() -> None:
    """Internship factor must be full when included and reduced when excluded."""
    resume = _full_resume()
    spec = _full_spec()
    ctx = _context()
    titles = FakeTitleTaxonomy()
    now = date(2026, 8, 29)
    included = s4_build_intervals(
        resume,
        spec,
        ctx,
        titles,
        now,
        ExperienceRequirement(min_years=5, target_years=8, count_internships=True),
    )
    excluded = s4_build_intervals(
        resume,
        spec,
        ctx,
        titles,
        now,
        ExperienceRequirement(min_years=5, target_years=8, count_internships=False),
    )
    assert any(i.internship_factor == 1.0 for i in included)
    assert any(i.internship_factor < 1.0 for i in excluded)


def test_s4_title_similarity_missing_inputs() -> None:
    """Title similarity must be zero when inputs are missing."""
    titles = FakeTitleTaxonomy()
    assert s4_title_similarity(ExperienceEntry(), "Engineer", titles) == pytest.approx(
        0.0, abs=1e-6
    )
    assert s4_title_similarity(
        ExperienceEntry(title_raw="Engineer"), None, titles
    ) == pytest.approx(0.0, abs=1e-6)


def test_s5_role_alignment_missing_inputs() -> None:
    """Role alignment must be zero when target or role title is missing."""
    titles = FakeTitleTaxonomy()
    role = ExperienceEntry(title_raw="Engineer")
    assert s5_role_alignment(role, titles, None, date(2026, 8, 29)) == pytest.approx(0.0, abs=1e-6)
    assert s5_role_alignment(
        ExperienceEntry(), titles, titles.normalise("Engineer"), date(2026, 8, 29)
    ) == pytest.approx(0.0, abs=1e-6)


def test_s7_education_more_branches() -> None:
    """Education component must cover required_level zero, fallback ratio and equivalent experience."""
    ctx = _context()
    base = _full_resume()

    # Unknown required level -> neutral.
    spec_unknown = _full_spec().model_copy(
        update={"education": EducationRequirement(min_level="unknown", fields=())}
    )
    assert s7_education_component(base, spec_unknown, ctx) == pytest.approx(1.0, abs=1e-6)

    # No candidate education -> 0.20 floor.
    spec_master = _full_spec().model_copy(
        update={"education": EducationRequirement(min_level="master", fields=())}
    )
    no_edu = base.model_copy(update={"education": ()})
    assert s7_education_component(no_edu, spec_master, ctx) == pytest.approx(0.20, abs=1e-6)

    # Equivalent experience fallback: bachelor vs master with 24 months timeline.
    equiv_resume = base.model_copy(
        update={
            "education": (EducationEntry(degree_level="bachelor", field="computer science"),),
            "timeline": Timeline(total_months_covered=24),
        }
    )
    equiv_spec = _full_spec().model_copy(
        update={
            "education": EducationRequirement(
                min_level="master", fields=(), equivalent_experience_allowed=True
            ),
            "experience": None,
        }
    )
    assert s7_education_component(equiv_resume, equiv_spec, ctx) == pytest.approx(0.70, abs=1e-6)


def test_s7_certification_more_branches() -> None:
    """Certification component must be zero without certs and handle in-progress."""
    spec = _full_spec()
    now = date(2026, 8, 29)
    resume_with_progress = _full_resume().model_copy(
        update={
            "certifications": (
                Certification(name="AWS", canonical="aws-certified", status="in-progress"),
            )
        }
    )
    assert s7_certification_component(resume_with_progress, spec, now) == pytest.approx(
        0.5, abs=1e-6
    )

    resume_no_certs = _full_resume().model_copy(update={"certifications": ()})
    assert s7_certification_component(resume_no_certs, spec, now) == pytest.approx(0.0, abs=1e-6)


def test_evidence_helpers_more() -> None:
    """Best match and evidence helpers must handle empty and dated cases."""
    ctx = _context()
    now = date(2026, 8, 29)
    assert _best_match_value((), now, ctx.config, ctx.ontology) == (0.0, None)
    assert _to_evidence(None) == ()

    skill = SkillMention(
        raw="Python", canonical="python", sections=("skills",), last_used="2026-08"
    )
    ev = _evidence_from_mention("python", skill, ctx.ontology)
    assert ev is not None
    assert _to_evidence(ev)[0].quote == "Python"

    rec, ev_rec = recency_for_skill(
        _full_resume(), "nonexistent", now, ctx.config.recency, ctx.ontology
    )
    assert rec == pytest.approx(0.0, abs=1e-6)
    assert ev_rec is None


def test_aggregate_penalty_cap_and_zero_weights() -> None:
    """Aggregation must cap penalties and ignore unavailable/zero-weighted dims."""
    cfg = ScoringConfig()
    integrity = IntegrityConfig(penalties={"DODGY": 8.0}, penalty_total_cap=10.0)
    findings = (
        IntegrityFinding(detector="fake", code="DODGY", message="bad"),
        IntegrityFinding(detector="fake", code="DODGY", message="bad"),
    )
    sub_scores = {
        "a": SubScore(dimension="a", value=100.0, weight=1.0, evidence=(), details=()),
        "zero": SubScore(dimension="zero", value=50.0, weight=1.0, evidence=(), details=()),
    }
    weights = {"a": 1.0, "zero": 0.0}
    agg = aggregate(sub_scores, weights, findings, cfg, integrity)
    assert agg.integrity_penalty == pytest.approx(10.0, abs=1e-6)
    assert agg.composite == pytest.approx(90.0, abs=1e-6)


# --- Targeted mutmut killers -------------------------------------------------


def test_score_skill_coverage_details_kill_continue_and_details() -> None:
    """Skill coverage details must be exact and continue on gaps."""
    ctx = _context()
    resume = _full_resume()

    unmatched = (
        RequiredSkill(canonical="tensorflow", weight=3),
        RequiredSkill(canonical="python", weight=5),
    )
    score, evidence, matches, gaps = score_skill_coverage(resume, unmatched, ctx)
    # First skill has no evidence, second is matched: continue must not stop the loop.
    assert score > 0.0
    assert len(gaps) == 1
    gap = gaps[0]
    assert isinstance(gap, GapDetail)
    assert gap.match == pytest.approx(0.0, abs=1e-6)
    assert gap.searched == ("tensorflow",)
    assert gap.note == "no evidence found"

    matched = (RequiredSkill(canonical="python", weight=5),)
    score2, evidence2, matches2, _ = score_skill_coverage(resume, matched, ctx)
    assert score2 > 0.0
    assert len(matches2) == 1
    detail = matches2[0]
    assert isinstance(detail, MatchDetail)
    assert detail.route is not None
    assert detail.evidence != ()
    assert evidence2 != ()


def test_s7_certification_component_weighted_multiple() -> None:
    """Certification component must weight multiple requirements correctly."""
    now = date(2026, 8, 29)
    resume = _full_resume().model_copy(
        update={
            "certifications": (
                Certification(name="AWS", canonical="aws-certified", status="active"),
            )
        }
    )
    spec = _full_spec().model_copy(
        update={
            "certifications": (
                {"name": "AWS", "canonical": "aws-certified", "weight": 2},
                {"name": "GCP", "canonical": "gcp-certified", "weight": 3},
            )
        }
    )
    assert s7_certification_component(resume, spec, now) == pytest.approx(0.4, abs=1e-6)

    # Total weight zero must return neutral (1.0).
    zero_weight_spec = _full_spec().model_copy(
        update={"certifications": ({"name": "GCP", "canonical": "gcp-certified", "weight": 0},)}
    )
    assert s7_certification_component(resume, zero_weight_spec, now) == pytest.approx(1.0, abs=1e-6)

    # Missing weight key should default to 1, not 2.
    no_weight_spec = _full_spec().model_copy(
        update={"certifications": ({"name": "AWS", "canonical": "aws-certified"},)}
    )
    assert s7_certification_component(resume, no_weight_spec, now) == pytest.approx(1.0, abs=1e-6)

    # String weight values should not be treated as numbers.
    string_weight_spec = _full_spec().model_copy(
        update={"certifications": ({"name": "AWS", "canonical": "aws-certified", "weight": "2"},)}
    )
    assert s7_certification_component(resume, string_weight_spec, now) == pytest.approx(
        1.0, abs=1e-6
    )


def test_s7_match_certification_edge_cases() -> None:
    """Match certification must handle name-only, continue, and exact-expiry cases."""
    now = date(2026, 8, 29)

    # Canonical None, name matches target.
    name_only = s7_match_certification(
        "aws-certified", (Certification(name="aws-certified", canonical=None),), now
    )
    assert name_only == pytest.approx(1.0, abs=1e-6)

    # First cert mismatched, second matched: continue must not break.
    continue_case = s7_match_certification(
        "aws-certified",
        (
            Certification(name="GCP", canonical="gcp-certified"),
            Certification(name="AWS", canonical="aws-certified"),
        ),
        now,
    )
    assert continue_case == pytest.approx(1.0, abs=1e-6)

    # Expiry exactly on the scoring date is still valid.
    exact_expiry = s7_match_certification(
        "aws-certified",
        (Certification(name="AWS", canonical="aws-certified", expires="2026-08-29"),),
        now,
    )
    assert exact_expiry == pytest.approx(1.0, abs=1e-6)

    # Empty target with a non-empty cert list should stay zero.
    assert s7_match_certification(
        "", (Certification(name="AWS", canonical="aws-certified"),), now
    ) == pytest.approx(0.0, abs=1e-6)


def test_s7_education_component_empty_fields_and_ratio() -> None:
    """Education component must treat empty fields as matched and clamp the ratio."""
    ctx = _context()
    base = _full_resume()

    # Empty accepted fields -> has_field True, matched level returns 1.0.
    spec_empty_fields = _full_spec().model_copy(
        update={"education": EducationRequirement(min_level="bachelor", fields=())}
    )
    assert s7_education_component(base, spec_empty_fields, ctx) == pytest.approx(1.0, abs=1e-6)

    # Higher level with no candidate field and required fields: ratio clamped at 1.0.
    higher_no_field = base.model_copy(
        update={
            "education": (EducationEntry(degree_level="phd"),),
        }
    )
    spec_bachelor_field = _full_spec().model_copy(
        update={
            "education": EducationRequirement(min_level="bachelor", fields=("computer science",))
        }
    )
    assert s7_education_component(higher_no_field, spec_bachelor_field, ctx) == pytest.approx(
        1.0, abs=1e-6
    )


# --- Third wave: exact boundary and detail killers ---------------------------


def test_s3_resume_and_jd_chunks_origin_ids() -> None:
    """Chunk builders must produce correct origin ids."""
    spec = _full_spec()
    jd = s3_jd_chunks(spec)
    assert any(c.origin_id == "required:python" for c in jd)
    assert any(c.origin_id == "preferred:sql" for c in jd)
    assert all(c.source == "jobspec" for c in jd)

    resume = _full_resume()
    resume_chunks = s3_resume_chunks(resume)
    assert any(c.origin_id == "experience:0" for c in resume_chunks)
    assert any(c.origin_id == "project:0" for c in resume_chunks)
    assert any(c.origin_id == "summary:headline" for c in resume_chunks)


def test_best_match_value_last_used_and_timeless() -> None:
    """Best match must differ when last_used is missing or the skill is timeless."""
    ctx = _context()
    ontology = ctx.ontology
    now = date(2026, 8, 29)

    timeless_recent = SkillMention(
        raw="Python", canonical="python", sections=("skills", "experience"), last_used="2026-08"
    )
    timeless_ev = _evidence_from_mention("python", timeless_recent, ontology)
    assert timeless_ev is not None
    m, _ = _best_match_value((timeless_ev,), now, ctx.config, ontology)
    assert m == pytest.approx(0.8, abs=1e-6)

    # Non-timeless skill at a recency above the floor: mutating to timeless half-life would raise it.
    non_timeless_moderate = SkillMention(
        raw="Kafka", canonical="kafka", sections=("skills", "experience"), last_used="2024-08"
    )
    non_timeless_ev = _evidence_from_mention("kafka", non_timeless_moderate, ontology)
    assert non_timeless_ev is not None
    m2, _ = _best_match_value((non_timeless_ev,), now, ctx.config, ontology)
    expected_kafka = 0.8 * math.exp(-math.log(2) * 2.0 / 4.0)
    assert m2 == pytest.approx(expected_kafka, abs=1e-6)

    # Non-timeless skill old enough to hit the recency floor.
    non_timeless_old = SkillMention(
        raw="Kafka", canonical="kafka", sections=("skills", "experience"), last_used="2010-01"
    )
    non_timeless_old_ev = _evidence_from_mention("kafka", non_timeless_old, ontology)
    assert non_timeless_old_ev is not None
    m2_old, _ = _best_match_value((non_timeless_old_ev,), now, ctx.config, ontology)
    assert m2_old == pytest.approx(0.4, abs=1e-6)

    no_last_used = SkillMention(raw="Python", canonical="python", sections=("skills", "experience"))
    no_last_ev = _evidence_from_mention("python", no_last_used, ontology)
    assert no_last_ev is not None
    m3, _ = _best_match_value((no_last_ev,), now, ctx.config, ontology)
    assert m3 == pytest.approx(0.8, abs=1e-6)


def test_s5_s6_recency_weight_exact_decay() -> None:
    """Recency weight must use the exact 365.2425 day divisor."""
    now = date(2026, 8, 29)
    one_year_ago = ExperienceEntry(end=DateValue(value="2025-08-29", precision=DatePrecision.DAY))
    dt_years = 365 / 365.2425
    expected = math.exp(-math.log(2) * dt_years / 2.0)
    assert s5_recency_weight(one_year_ago, now, 2.0, 0.2) == pytest.approx(expected, abs=1e-6)
    assert s6_recency_weight(one_year_ago, now, 2.0, 0.2) == pytest.approx(expected, abs=1e-6)


def test_s4_from_years_boundary_killers() -> None:
    """S4 from_years must use b=0 and exact multipliers."""
    disabled = OverqualificationConfig(enabled=False)
    # b == 0 is treated as b == a; mutating that changes the result.
    assert s4_from_years(4.0, 5, 0, disabled) == pytest.approx(58.0, abs=1e-6)
    assert s4_from_years(3.0, 6, 0, disabled) == pytest.approx(40.0, abs=1e-6)

    # Multipliers below half_a must be exact.
    assert s4_from_years(2.0, 10, 12, disabled) == pytest.approx(40.0 * (2.0 / 5.0), abs=1e-6)

    # n == b with overqualification enabled must not decay.
    enabled = OverqualificationConfig(enabled=True, cap=10, points_per_year=3)
    assert s4_from_years(8.0, 5, 8, enabled) == pytest.approx(100.0, abs=1e-6)

    # Overqualification floor must be allowed to fall below 1.
    heavy = OverqualificationConfig(enabled=True, cap=100, points_per_year=50)
    assert s4_from_years(10.0, 5, 5, heavy) == pytest.approx(0.0, abs=1e-6)


def test_s9_stability_component_median_and_continue() -> None:
    """Stability must use exact median thresholds and continue past contract roles."""
    now = date(2026, 8, 29)
    base = _full_resume()

    # Median exactly 24 months -> 1.0
    exact_24 = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    start=DateValue(value="2024-08", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
                ExperienceEntry(
                    start=DateValue(value="2024-08", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_stability_component(exact_24, now) == pytest.approx(1.0, abs=1e-6)

    # Median exactly 12 months -> 0.75
    exact_12 = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    start=DateValue(value="2025-08", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
                ExperienceEntry(
                    start=DateValue(value="2025-08", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_stability_component(exact_12, now) == pytest.approx(0.75, abs=1e-6)

    # Contract role followed by a full-time role must continue and evaluate the full-time role.
    mixed = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    employment_type=EmploymentType.CONTRACT,
                    start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                    end=DateValue(value="2021-01", precision=DatePrecision.MONTH),
                ),
                ExperienceEntry(
                    start=DateValue(value="2024-08", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_stability_component(mixed, now) == pytest.approx(1.0, abs=1e-6)

    # Invalid dates in a full-time role must not abort the loop.
    invalid = base.model_copy(
        update={
            "experience": (
                ExperienceEntry(
                    employment_type=EmploymentType.FULL_TIME,
                    start=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                    end=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                ),
                ExperienceEntry(
                    start=DateValue(value="2024-08", precision=DatePrecision.MONTH),
                    end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
                ),
            )
        }
    )
    assert s9_stability_component(invalid, now) == pytest.approx(1.0, abs=1e-6)


# --- S5 / S6 / S10 helpers --------------------------------------------------


def test_s5_role_alignment() -> None:
    """Role alignment must combine title similarity, seniority factor and recency."""
    titles = FakeTitleTaxonomy()
    role = ExperienceEntry(
        title_raw="Software Engineer",
        seniority="senior",
        end=DateValue(value="2026-08", precision=DatePrecision.MONTH),
    )
    target = titles.normalise("Software Engineer")
    assert target is not None
    score = s5_role_alignment(role, titles, target, date(2026, 8, 29))
    assert score > 0.0


def test_s6_domain_match() -> None:
    """Domain match must return exact, adjacent and floor values."""
    exact = ExperienceEntry(title_family="software engineering", title_raw="Engineer")
    assert s6_domain_match(exact, "software engineering") == pytest.approx(1.0, abs=1e-6)
    adjacent = ExperienceEntry(title_family="software", title_raw="Engineer")
    assert s6_domain_match(adjacent, "software engineering") == pytest.approx(0.60, abs=1e-6)
    unrelated = ExperienceEntry(title_family="sales", title_raw="Rep")
    assert s6_domain_match(unrelated, "software engineering") == pytest.approx(0.20, abs=1e-6)


def test_s10_is_unparseable() -> None:
    """Parseability helper must identify missing and unknown dates."""
    assert s10_is_unparseable(None) is True
    assert s10_is_unparseable(DateValue(value=None, precision=DatePrecision.UNKNOWN)) is True
    assert s10_is_unparseable(DateValue(value="2026-08", precision=DatePrecision.MONTH)) is False


# --- Additional S7 education helpers ----------------------------------------


def test_s7_education_component_branches() -> None:
    """Education component must handle all requirement/qualification branches."""
    resume = _full_resume()
    ctx = _context()

    # No education requirement is neutral.
    spec_no_edu = _full_spec().model_copy(update={"education": None})
    assert s7_education_component(resume, spec_no_edu, ctx) == pytest.approx(1.0, abs=1e-6)

    # Matched level and field.
    spec = _full_spec()
    assert s7_education_component(resume, spec, ctx) == pytest.approx(1.0, abs=1e-6)

    # Adjacent field (candidate has CS, requirement asks for physics).
    spec_adjacent = spec.model_copy(
        update={
            "education": EducationRequirement(
                min_level="bachelor", fields=("physics",), equivalent_experience_allowed=True
            )
        }
    )
    assert s7_education_component(resume, spec_adjacent, ctx) == pytest.approx(0.80, abs=1e-6)

    # Higher required level than possessed: ratio branch.
    spec_higher = spec.model_copy(
        update={
            "education": EducationRequirement(
                min_level="master", fields=("computer science",), equivalent_experience_allowed=True
            )
        }
    )
    assert s7_education_component(resume, spec_higher, ctx) == pytest.approx(0.75, abs=1e-6)


def test_s7_certification_component_branches() -> None:
    """Certification component must be neutral when no certs are required."""
    resume = _full_resume()
    spec = _full_spec()
    now = date(2026, 8, 29)
    assert s7_certification_component(resume, spec, now) == pytest.approx(1.0, abs=1e-6)

    spec_no_certs = spec.model_copy(update={"certifications": ()})
    assert s7_certification_component(resume, spec_no_certs, now) == pytest.approx(1.0, abs=1e-6)

    resume_no_certs = resume.model_copy(update={"certifications": ()})
    assert s7_certification_component(resume_no_certs, spec, now) < 1.0


@pytest.mark.parametrize(
    ("target", "candidate_cert", "expected_factor"),
    [
        ("", Certification(name="AWS", canonical="aws-certified"), 0.0),
        ("aws-certified", Certification(name="AWS", canonical="aws-certified"), 1.0),
        (
            "aws-certified",
            Certification(name="AWS", canonical="aws-certified", expires="2020-05"),
            0.40,
        ),
        (
            "aws-certified",
            Certification(name="AWS", canonical="aws-certified", status="in-progress"),
            0.50,
        ),
        ("aws-certified", (), 0.0),
    ],
)
def test_s7_match_certification_branches(
    target: str, candidate_cert: Certification | tuple[()], expected_factor: float
) -> None:
    """Certification matching must handle target, expiry, in-progress and absence."""
    certs = candidate_cert if isinstance(candidate_cert, tuple) else (candidate_cert,)
    assert s7_match_certification(target, certs, date(2026, 8, 29)) == pytest.approx(
        expected_factor, abs=1e-6
    )


def test_s7_cert_name() -> None:
    """Cert name extraction must prefer canonical, then name, then title."""
    assert s7_cert_name({"canonical": "aws"}) == "aws"
    assert s7_cert_name({"name": "AWS Certified"}) == "aws certified"
    assert s7_cert_name({"title": "AWS Solutions Architect"}) == "aws solutions architect"
    assert s7_cert_name({}) == ""


def test_s7_degree_ordinal() -> None:
    """Degree ordinal mapping must cover the common levels."""
    assert s7_degree_ordinal("bachelor") == 3
    assert s7_degree_ordinal("master") == 4
    assert s7_degree_ordinal("phd") == 5
    assert s7_degree_ordinal(None) == 0
    assert s7_degree_ordinal("unknown") == 0


# --- Additional S4 experience helpers ---------------------------------------


def test_s4_from_years_branches() -> None:
    """S4 band conversion must hit the zero, equal and overqualification branches."""
    disabled = OverqualificationConfig(enabled=False)
    assert s4_from_years(0.0, 0, 0, disabled) == pytest.approx(70.0, abs=1e-6)
    assert s4_from_years(5.0, 5, 5, disabled) == pytest.approx(100.0, abs=1e-6)

    enabled = OverqualificationConfig(enabled=True, cap=10, points_per_year=3)
    assert s4_from_years(11.0, 5, 8, enabled) == pytest.approx(91.0, abs=1e-6)
    assert s4_from_years(20.0, 5, 8, enabled) == pytest.approx(90.0, abs=1e-6)


def test_s4_relevant_and_raw_years() -> None:
    """Relevant and raw years must be derived from interval lists."""
    interval = S4Interval(
        start_year=2020,
        start_month=1,
        end_year=2020,
        end_month=6,
        relevance=1.0,
        internship_factor=1.0,
    )
    assert s4_relevant_years((interval,)) == pytest.approx(6 / 12.0, abs=1e-6)
    assert s4_raw_years((interval,)) == pytest.approx(6 / 12.0, abs=1e-6)

    zero_relevance = S4Interval(
        start_year=2020,
        start_month=1,
        end_year=2021,
        end_month=1,
        relevance=0.0,
        internship_factor=1.0,
    )
    assert s4_relevant_years((zero_relevance,)) == pytest.approx(0.0, abs=1e-6)
    assert s4_raw_years((zero_relevance,)) == pytest.approx(1.0 + 1 / 12.0, abs=1e-6)


def test_s4_build_intervals_internship() -> None:
    """Internship roles must carry a reduced internship factor."""
    resume = _full_resume()
    spec = _full_spec()
    ctx = _context()
    titles = FakeTitleTaxonomy()
    now = date(2026, 8, 29)
    req = ExperienceRequirement(min_years=5, target_years=8, count_internships=False)
    intervals = s4_build_intervals(resume, spec, ctx, titles, now, req)
    assert any(i.internship_factor < 1.0 for i in intervals)
    assert all(i.relevance >= 0.0 for i in intervals)


def test_s4_title_similarity() -> None:
    """Title similarity must match exact and penalise unrelated titles."""
    titles = FakeTitleTaxonomy()
    role = ExperienceEntry(title_raw="Software Engineer")
    assert s4_title_similarity(role, "Software Engineer", titles) == pytest.approx(1.0, abs=1e-6)
    assert s4_title_similarity(role, "Other", titles) == pytest.approx(0.15, abs=1e-6)


def test_s4_domain_similarity() -> None:
    """Domain similarity must return exact match or the floor."""
    exact = ExperienceEntry(title_family="software engineering")
    assert s4_domain_similarity(exact, "software engineering") == pytest.approx(1.0, abs=1e-6)
    assert s4_domain_similarity(exact, "sales") == pytest.approx(0.20, abs=1e-6)
    assert s4_domain_similarity(exact, None) == pytest.approx(1.0, abs=1e-6)


def test_s4_skill_overlap() -> None:
    """Skill overlap must handle missing requirements and missing skills."""
    role_with_skills = ExperienceEntry(skills_evidenced=("python", "apache-spark"))
    spec = JobSpec(
        job_id="x",
        title="Engineer",
        required_skills=(
            RequiredSkill(canonical="python", weight=5),
            RequiredSkill(canonical="kafka", weight=3),
        ),
    )
    assert s4_skill_overlap(role_with_skills, spec) == pytest.approx(0.5, abs=1e-6)

    role_no_skills = ExperienceEntry()
    spec_no_required = JobSpec(job_id="x", title="Engineer")
    assert s4_skill_overlap(role_no_skills, spec_no_required) == pytest.approx(1.0, abs=1e-6)


# --- Additional S5 / S6 helpers ---------------------------------------------


def test_s5_recency_weight_branches() -> None:
    """Recency weight must treat present, open-ended and future roles as fully relevant."""
    now = date(2026, 8, 29)
    present = ExperienceEntry(end=DateValue(value=None, precision=DatePrecision.PRESENT))
    assert s5_recency_weight(present, now, 6.0, 0.55) == pytest.approx(1.0, abs=1e-6)

    open_ended = ExperienceEntry(end=None)
    assert s5_recency_weight(open_ended, now, 6.0, 0.55) == pytest.approx(1.0, abs=1e-6)

    future = ExperienceEntry(end=DateValue(value="2027-08", precision=DatePrecision.MONTH))
    assert s5_recency_weight(future, now, 6.0, 0.55) == pytest.approx(1.0, abs=1e-6)


def test_s5_role_alignment_unrelated() -> None:
    """Role alignment must apply the floor title similarity for unrelated titles."""
    titles = FakeTitleTaxonomy()
    role = ExperienceEntry(
        title_raw="Sales Representative",
        seniority="senior",
        end=DateValue(value=None, precision=DatePrecision.PRESENT),
    )
    target = titles.normalise("Software Engineer")
    assert target is not None
    assert s5_role_alignment(role, titles, target, date(2026, 8, 29)) == pytest.approx(
        0.15, abs=1e-6
    )


def test_s6_domain_match_and_recency() -> None:
    """Domain match must hit exact, adjacent and floor values; recency weight works."""
    exact = ExperienceEntry(title_family="software engineering")
    assert s6_domain_match(exact, "software engineering") == pytest.approx(1.0, abs=1e-6)
    adjacent = ExperienceEntry(title_family="software")
    assert s6_domain_match(adjacent, "software engineering") == pytest.approx(0.60, abs=1e-6)
    unrelated = ExperienceEntry(title_family="sales")
    assert s6_domain_match(unrelated, "software engineering") == pytest.approx(0.20, abs=1e-6)

    now = date(2026, 8, 29)
    present = ExperienceEntry(end=DateValue(value=None, precision=DatePrecision.PRESENT))
    assert s6_recency_weight(present, now, 6.0, 0.55) == pytest.approx(1.0, abs=1e-6)
