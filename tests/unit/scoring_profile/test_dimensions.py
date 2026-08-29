from __future__ import annotations

import pytest
from tests.fakes import FakeEmbeddingClient, FakeOntology, FakeTitleTaxonomy

from ats_scan.models.config import ScoringConfig
from ats_scan.models.jobspec import (
    DomainRequirement,
    EducationRequirement,
    ExperienceRequirement,
    JobSpec,
    RequiredSkill,
)
from ats_scan.models.resume import (
    Bullet,
    CanonicalResume,
    Certification,
    DatePrecision,
    DateValue,
    EducationEntry,
    ExperienceEntry,
    ExtractionMetadata,
    SkillMention,
    Timeline,
)
from ats_scan.models.run import ScoringContext
from ats_scan.scoring.dimensions.s4_experience import S4Experience
from ats_scan.scoring.dimensions.s5_title import S5Title
from ats_scan.scoring.dimensions.s6_domain import S6Domain
from ats_scan.scoring.dimensions.s7_education import S7Education
from ats_scan.scoring.dimensions.s9_trajectory import S9Trajectory
from ats_scan.scoring.dimensions.s10_parseability import S10Parseability


@pytest.fixture
def ctx() -> ScoringContext:
    return ScoringContext(
        ontology=FakeOntology(),
        titles=FakeTitleTaxonomy(),
        embeddings=FakeEmbeddingClient(),
        llm=None,
        config=ScoringConfig(),
        now="2026-08-29",
    )


def _date(value: str | None, precision: DatePrecision = DatePrecision.MONTH) -> DateValue:
    return DateValue(value=value, precision=precision)


def _role(
    start: str,
    end: str | None = None,
    title: str = "Senior Data Engineer",
    title_family: str = "data_engineering",
    skills: tuple[str, ...] = (),
    seniority: str | None = None,
) -> ExperienceEntry:
    end_value = (
        DateValue(value=end, precision=DatePrecision.MONTH)
        if end
        else DateValue(value=None, precision=DatePrecision.PRESENT)
    )
    return ExperienceEntry(
        employer="Acme",
        title_raw=title,
        title_family=title_family,
        seniority=seniority,
        start=_date(start),
        end=end_value,
        bullets=(Bullet(text=f"{title} at Acme", span=(0, 16)),),
        skills_evidenced=skills,
    )


def _resume(*roles: ExperienceEntry) -> CanonicalResume:
    return CanonicalResume(
        candidate_id="c_test",
        experience=roles,
    )


def _spec(
    min_years: int = 5,
    target_years: int = 8,
    title: str = "Senior Data Engineer",
    title_family: str = "data_engineering",
    domain: str | None = None,
    required_skills: tuple[str, ...] = (),
) -> JobSpec:
    domain_req = None
    if domain is not None:
        domain_req = DomainRequirement(industry=domain, required=False)
    return JobSpec(
        job_id="jd_test",
        title=title,
        title_family=title_family,
        domain=domain_req,
        experience=ExperienceRequirement(min_years=min_years, target_years=target_years),
        required_skills=tuple(
            RequiredSkill(canonical=skill, weight=5) for skill in required_skills
        ),
    )


class TestS4Experience:
    """TRD §5.3.4 — relevant experience depth piecewise mapping."""

    def test_s4_at_minimum(self, ctx: ScoringContext) -> None:
        """At n == a the score reaches 70."""
        # 60 months from 2021-09 to 2026-08 => n = 5.0 when relevance is 1.
        resume = _resume(_role("2021-09", None, skills=("python",), title_family="logistics"))
        spec = _spec(min_years=5, target_years=8, domain="logistics", required_skills=("python",))
        score = S4Experience().score(resume, spec, ctx)
        assert score.value == pytest.approx(70.0, abs=0.5)

    def test_s4_at_target(self, ctx: ScoringContext) -> None:
        """At n == b the score reaches 100."""
        resume = _resume(_role("2018-08", None, skills=("python",), title_family="logistics"))
        spec = _spec(min_years=5, target_years=8, domain="logistics", required_skills=("python",))
        score = S4Experience().score(resume, spec, ctx)
        assert score.value == pytest.approx(100.0, abs=0.5)

    def test_s4_below_half_minimum(self, ctx: ScoringContext) -> None:
        """n < 0.5a maps to the first branch 0..40."""
        # 30 months from 2024-03 to 2026-08 => n = 2.5, a=5, half_a=2.5.
        resume = _resume(_role("2024-03", None, skills=("python",), title_family="logistics"))
        spec = _spec(min_years=5, target_years=8, domain="logistics", required_skills=("python",))
        score = S4Experience().score(resume, spec, ctx)
        assert score.value == pytest.approx(40.0, abs=0.5)

    def test_s4_overqualified_disabled(self, ctx: ScoringContext) -> None:
        """Over-qualification decay is off by default, so n > b still scores 100."""
        resume = _resume(_role("2015-01", None, skills=("python",), title_family="logistics"))
        spec = _spec(min_years=5, target_years=8, domain="logistics", required_skills=("python",))
        score = S4Experience().score(resume, spec, ctx)
        assert score.value == pytest.approx(100.0, abs=0.5)

    def test_s4_overqualified_enabled(self, ctx: ScoringContext) -> None:
        """When enabled, over-qualification decay is applied."""
        ctx.config.experience.overqualification.enabled = True
        ctx.config.experience.overqualification.cap = 15
        ctx.config.experience.overqualification.points_per_year = 3
        # 13.6 years over target: decay capped at 15 points.
        resume = _resume(_role("2013-01", None, skills=("python",), title_family="logistics"))
        spec = _spec(min_years=5, target_years=8, domain="logistics", required_skills=("python",))
        score = S4Experience().score(resume, spec, ctx)
        assert score.value == pytest.approx(85.0, abs=0.5)

    def test_s4_no_minimum_guard(self, ctx: ScoringContext) -> None:
        """a == 0 returns a neutral 70 instead of dividing by zero."""
        resume = _resume(_role("2020-01", None))
        spec = _spec(min_years=0, target_years=0)
        score = S4Experience().score(resume, spec, ctx)
        assert score.value == pytest.approx(70.0, abs=0.1)


class TestS5Title:
    """TRD §5.3.5 — role and title alignment."""

    def test_s5_exact_current_role(self, ctx: ScoringContext) -> None:
        """Exact title, target seniority, current role => 100."""
        resume = _resume(_role("2020-01", None, title="Senior Data Engineer"))
        spec = _spec(title="Senior Data Engineer")
        score = S5Title().score(resume, spec, ctx)
        assert score.value == pytest.approx(100.0, abs=0.1)

    def test_s5_unrelated_role(self, ctx: ScoringContext) -> None:
        """Unrelated family title scores the low similarity factor."""
        resume = _resume(_role("2020-01", None, title="Nurse"))
        spec = _spec(title="Senior Data Engineer")
        score = S5Title().score(resume, spec, ctx)
        assert score.value == pytest.approx(15.0, abs=0.5)


class TestS6Domain:
    """TRD §5.3.6 — domain and industry match."""

    def test_s6_exact_match(self, ctx: ScoringContext) -> None:
        """Exact domain match in a current role => 100."""
        resume = _resume(_role("2020-01", None, title_family="logistics"))
        spec = _spec(domain="logistics")
        score = S6Domain().score(resume, spec, ctx)
        assert score.value == pytest.approx(100.0, abs=0.1)

    def test_s6_excluded_when_weight_zero(self, ctx: ScoringContext) -> None:
        """S6 is excluded when the domain is not required and its weight is 0."""
        ctx.config.weights["S6"] = 0
        resume = _resume(_role("2020-01", None, title_family="logistics"))
        spec = _spec(domain="logistics")
        score = S6Domain().score(resume, spec, ctx)
        assert score.value is None

    def test_s6_floor(self, ctx: ScoringContext) -> None:
        """No domain evidence still hits the 0.20 floor."""
        resume = _resume(_role("2020-01", None, title_family="healthcare"))
        spec = _spec(domain="logistics")
        score = S6Domain().score(resume, spec, ctx)
        assert score.value == pytest.approx(20.0, abs=0.1)


class TestS7Education:
    """TRD §5.3.7 — education and certifications."""

    def test_s7_exact_degree_and_field(self, ctx: ScoringContext) -> None:
        """Required level and field met => 100."""
        resume = CanonicalResume(
            candidate_id="c_test",
            education=(
                EducationEntry(
                    degree_level="bachelors", field="computer science", end=_date("2020-05")
                ),
            ),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            education=EducationRequirement(
                min_level="bachelors",
                fields=("computer science",),
            ),
        )
        score = S7Education().score(resume, spec, ctx)
        assert score.value == pytest.approx(100.0, abs=0.1)

    def test_s7_one_level_below_with_equivalent_experience(self, ctx: ScoringContext) -> None:
        """One level below with equivalent experience allowed => 0.70 education factor."""
        resume = CanonicalResume(
            candidate_id="c_test",
            experience=(_role("2016-01", None, skills=("python",)),),
            education=(
                EducationEntry(
                    degree_level="associates", field="computer science", end=_date("2016-05")
                ),
            ),
            timeline=Timeline(total_months_covered=60),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            experience=ExperienceRequirement(min_years=3, target_years=8),
            education=EducationRequirement(
                min_level="bachelors",
                fields=("computer science",),
                equivalent_experience_allowed=True,
            ),
        )
        score = S7Education().score(resume, spec, ctx)
        assert score.value == pytest.approx(82.0, abs=0.5)

    def test_s7_expired_cert(self, ctx: ScoringContext) -> None:
        """Expired certification counts at 0.40."""
        resume = CanonicalResume(
            candidate_id="c_test",
            certifications=(Certification(name="AWS SA", canonical="aws sa", expires="2020-06"),),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            certifications=({"canonical": "aws sa", "weight": 1},),
        )
        score = S7Education().score(resume, spec, ctx)
        # edu=1.0, cert=0.4 => 0.76 => 76.0
        assert score.value == pytest.approx(76.0, abs=0.1)


class TestS9Trajectory:
    """TRD §5.3.9 — career trajectory and stability."""

    def test_s9_rising_seniority(self, ctx: ScoringContext) -> None:
        """Rising seniority and long median tenure => high score."""
        resume = _resume(
            _role("2019-01", "2021-01", seniority="junior"),
            _role("2021-01", None, seniority="senior"),
        )
        spec = _spec()
        score = S9Trajectory().score(resume, spec, ctx)
        assert score.value == pytest.approx(100.0, abs=0.5)

    def test_s9_ignores_employment_gap(self, ctx: ScoringContext) -> None:
        """Injecting a 12-month gap does not change S9."""
        resume_no_gap = _resume(
            _role("2019-01", "2020-01", seniority="junior"),
            _role("2020-01", None, seniority="senior"),
        )
        resume_with_gap = _resume(
            _role("2019-01", "2020-01", seniority="junior"),
            _role("2022-01", None, seniority="senior"),
        )
        spec = _spec()
        score_a = S9Trajectory().score(resume_no_gap, spec, ctx)
        score_b = S9Trajectory().score(resume_with_gap, spec, ctx)
        assert score_a.value == score_b.value


class TestS10Parseability:
    """TRD §5.3.10 — resume parseability deductions."""

    def test_s10_native_text_clean(self, ctx: ScoringContext) -> None:
        """A clean resume with all sections and native text scores 100."""
        resume = CanonicalResume(
            candidate_id="c_test",
            extraction=ExtractionMetadata(method="native_text"),
            experience=(_role("2020-01", None),),
            skills=(SkillMention(raw="Python", canonical="python"),),
            education=(EducationEntry(degree_level="bachelors", field="computer science"),),
        )
        score = S10Parseability().score(resume, _spec(), ctx)
        assert score.value == 100.0

    def test_s10_ocr_deduction(self, ctx: ScoringContext) -> None:
        """OCR plus two missing sections deducts 70 points."""
        resume = CanonicalResume(
            candidate_id="c_test",
            extraction=ExtractionMetadata(method="ocr"),
            experience=(_role("2020-01", None),),
            skills=(),
            education=(),
        )
        score = S10Parseability().score(resume, _spec(), ctx)
        assert score.value == pytest.approx(30.0, abs=0.1)

    def test_s10_missing_sections_cap(self, ctx: ScoringContext) -> None:
        """Missing skills and education deducts 30 (capped) even if three are missing."""
        resume = CanonicalResume(
            candidate_id="c_test",
            extraction=ExtractionMetadata(method="native_text"),
            experience=(_role("2020-01", None),),
        )
        score = S10Parseability().score(resume, _spec(), ctx)
        # experience present, skills and education missing => -30
        assert score.value == pytest.approx(70.0, abs=0.1)

    def test_s10_floor(self, ctx: ScoringContext) -> None:
        """The score is floored at 0, never negative."""
        resume = CanonicalResume(
            candidate_id="c_test",
            extraction=ExtractionMetadata(method="ocr", columns_detected=3),
            experience=(
                ExperienceEntry(
                    employer="Acme",
                    title_raw="Engineer",
                    start=None,
                    end=None,
                ),
            ),
            skills=(),
            education=(),
        )
        score = S10Parseability().score(resume, _spec(), ctx)
        assert score.value == 0.0
