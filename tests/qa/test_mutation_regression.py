from __future__ import annotations

import pytest
from tests.fakes import FakeEmbeddingClient, FakeOntology, FakeTitleTaxonomy

from ats_scan.models.config import ScoringConfig
from ats_scan.models.jobspec import (
    DomainRequirement,
    EducationRequirement,
    ExperienceRequirement,
    JobSpec,
    PreferredSkill,
    RequiredSkill,
    ResponsibilityChunk,
)
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
)
from ats_scan.models.run import ScoringContext
from ats_scan.scoring.dimensions.s1_required_skills import S1RequiredSkills
from ats_scan.scoring.dimensions.s2_preferred_skills import S2PreferredSkills
from ats_scan.scoring.dimensions.s3_semantic import S3Semantic
from ats_scan.scoring.dimensions.s4_experience import S4Experience
from ats_scan.scoring.dimensions.s5_title import S5Title
from ats_scan.scoring.dimensions.s6_domain import S6Domain
from ats_scan.scoring.dimensions.s7_education import S7Education
from ats_scan.scoring.dimensions.s8_skill_recency import S8SkillRecency
from ats_scan.scoring.dimensions.s9_trajectory import S9Trajectory
from ats_scan.scoring.dimensions.s10_parseability import S10Parseability


def _context() -> ScoringContext:
    return ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=None,
        config=ScoringConfig(),
        now="2026-08-29",
    )


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


@pytest.mark.covers("FR-701")
def test_full_scoring_case() -> None:
    """Regression smoke that exercises many scoring branches on a rich resume."""
    resume = _full_resume()
    spec = _full_spec()
    ctx = _context()

    assert S1RequiredSkills().score(resume, spec, ctx).value == pytest.approx(80.0, abs=1e-6)
    assert S2PreferredSkills().score(resume, spec, ctx).value == pytest.approx(0.0, abs=1e-6)

    s3 = S3Semantic().score(resume, spec, ctx)
    assert s3.value == pytest.approx(5.693635875057952, abs=1e-6)
    assert s3.detail is not None
    assert s3.detail["chunk_counts"] == {"jd": 6, "resume": 4}
    assert s3.detail["raw"] == pytest.approx(0.2756213614377608, abs=1e-6)

    assert S4Experience().score(resume, spec, ctx).value == pytest.approx(43.62, abs=1e-2)
    assert S5Title().score(resume, spec, ctx).value == pytest.approx(14.87, abs=1e-2)
    assert S6Domain().score(resume, spec, ctx).value == pytest.approx(59.47, abs=1e-2)
    assert S7Education().score(resume, spec, ctx).value == pytest.approx(100.0, abs=1e-6)
    assert S8SkillRecency().score(resume, spec, ctx).value == pytest.approx(100.0, abs=1e-6)
    assert S9Trajectory().score(resume, spec, ctx).value == pytest.approx(72.5, abs=1e-2)
    assert S10Parseability().score(resume, spec, ctx).value == pytest.approx(45.0, abs=1e-6)
