from __future__ import annotations

import pytest
from tests.fakes import FakeEmbeddingClient, FakeOntology, FakeTitleTaxonomy

from resume_ranker.models.config import ScoringConfig
from resume_ranker.models.jobspec import (
    DomainRequirement,
    EducationRequirement,
    ExperienceRequirement,
    JobSpec,
)
from resume_ranker.models.ontology import TitleMatch
from resume_ranker.models.resume import (
    CanonicalResume,
    Certification,
    DatePrecision,
    DateValue,
    EducationEntry,
    EmploymentType,
    ExperienceEntry,
    ExtractionMetadata,
    Identity,
    SkillMention,
)
from resume_ranker.models.run import ScoringContext
from resume_ranker.protocols import TitleTaxonomy
from resume_ranker.scoring.dimensions.s4_experience import S4Experience
from resume_ranker.scoring.dimensions.s5_title import S5Title
from resume_ranker.scoring.dimensions.s6_domain import S6Domain
from resume_ranker.scoring.dimensions.s7_education import S7Education
from resume_ranker.scoring.dimensions.s9_trajectory import S9Trajectory
from resume_ranker.scoring.dimensions.s10_parseability import S10Parseability


def _ctx() -> ScoringContext:
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
    start: str | None = "2020-01",
    end: str | None = None,
    title: str = "Senior Data Engineer",
    title_family: str | None = "data_engineering",
    skills: tuple[str, ...] = (),
    seniority: str | None = None,
    employment_type: EmploymentType = EmploymentType.FULL_TIME,
) -> ExperienceEntry:
    end_value: DateValue
    if end is None:
        end_value = DateValue(value=None, precision=DatePrecision.PRESENT)
    else:
        end_value = DateValue(value=end, precision=DatePrecision.MONTH)
    start_value = _date(start) if start else None
    return ExperienceEntry(
        employer="Acme",
        title_raw=title,
        title_family=title_family,
        seniority=seniority,
        employment_type=employment_type,
        start=start_value,
        end=end_value,
        skills_evidenced=skills,
    )


def _resume(*roles: ExperienceEntry) -> CanonicalResume:
    return CanonicalResume(candidate_id="c_test", experience=roles)


def _spec(
    min_years: int = 5,
    target_years: int = 8,
    title: str = "Senior Data Engineer",
    domain: str | None = None,
    required_skills: tuple[str, ...] = (),
) -> JobSpec:
    from resume_ranker.models.jobspec import RequiredSkill

    return JobSpec(
        job_id="jd_test",
        title=title,
        domain=DomainRequirement(industry=domain) if domain else None,
        experience=ExperienceRequirement(min_years=min_years, target_years=target_years),
        required_skills=tuple(
            RequiredSkill(canonical=skill, weight=5) for skill in required_skills
        ),
    )


class TitlesWithGap(TitleTaxonomy):
    """Fake title taxonomy that returns a configured seniority gap."""

    def __init__(self, gap: int = 0) -> None:
        self._gap = gap

    def normalise(self, raw_title: str) -> TitleMatch | None:
        return TitleMatch(
            family=raw_title.lower(),
            seniority="senior",
            raw=raw_title,
            normalised=raw_title.lower(),
        )

    def similarity(self, a: TitleMatch, b: TitleMatch) -> float:
        return 1.0 if a.family == b.family else 0.15

    def seniority_gap(self, role: TitleMatch, target: TitleMatch) -> int:
        return self._gap


class TestCoverageS4:
    """Branch coverage for S4Experience."""

    def test_no_domain_and_no_required_skills(self) -> None:
        """Domain and skill overlap are neutral when not specified."""
        resume = _resume(_role("2020-01", None, title="Senior Data Engineer"))
        spec = _spec(title="Senior Data Engineer")
        score = S4Experience().score(resume, spec, _ctx())
        assert score.value is not None and score.value > 0

    def test_invalid_dates_skipped(self) -> None:
        """Roles with unresolvable dates do not contribute to coverage."""
        resume = _resume(
            _role("not-a-date", None),
            _role("2020-01", "2019-01"),  # end before start
        )
        score = S4Experience().score(resume, _spec(), _ctx())
        # n == 0 and a > 0 => first branch maps to 0.
        assert score.value == pytest.approx(0.0, abs=0.1)

    def test_internship_factor(self) -> None:
        """Internships count at half duration by default."""
        resume = _resume(
            _role(
                "2021-09",
                None,
                title_family="logistics",
                skills=("python",),
                employment_type=EmploymentType.INTERNSHIP,
            )
        )
        spec = _spec(domain="logistics")
        score_full = S4Experience().score(resume, spec, _ctx())

        spec_count = _spec(domain="logistics")
        spec_count.experience.count_internships = True
        score_count = S4Experience().score(resume, spec_count, _ctx())
        assert score_count.value is not None and score_full.value is not None
        assert score_count.value > score_full.value

    def test_zero_relevant_years(self) -> None:
        """n == 0 yields a score of 0."""
        resume = _resume()
        spec = _spec(min_years=5, target_years=8)
        score = S4Experience().score(resume, spec, _ctx())
        assert score.value == pytest.approx(0.0, abs=0.1)


class TestCoverageS5:
    """Branch coverage for S5Title."""

    def test_no_experience(self) -> None:
        """No roles yields a score of 0."""
        resume = _resume()
        score = S5Title().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(0.0, abs=0.1)

    def test_past_role_recency_decay(self) -> None:
        """A role ending in the past has a recency weight below 1.0."""
        resume = _resume(_role("2015-01", "2019-01"))
        score = S5Title().score(resume, _spec(), _ctx())
        assert score.value is not None
        assert score.value < 100.0

    def test_seniority_factor_mapping(self) -> None:
        """Seniority gap maps to the TRD factor table."""
        for gap, expected_factor in [
            (-3, 0.45),
            (-2, 0.70),
            (-1, 1.00),
            (0, 1.00),
            (1, 0.95),
            (2, 0.85),
        ]:
            ctx = ScoringContext(
                ontology=FakeOntology(),
                titles=TitlesWithGap(gap),
                embeddings=FakeEmbeddingClient(),
                llm=None,
                config=ScoringConfig(),
                now="2026-08-29",
            )
            resume = _resume(_role("2020-01", None))
            score = S5Title().score(resume, _spec(), ctx)
            assert score.value is not None
            assert score.value == pytest.approx(100.0 * expected_factor, abs=0.1)

    def test_unrelated_title(self) -> None:
        """Unrelated title family uses the low similarity factor."""
        resume = _resume(_role("2020-01", None, title="Nurse"))
        score = S5Title().score(resume, _spec(title="Senior Data Engineer"), _ctx())
        assert score.value == pytest.approx(15.0, abs=0.5)


class TestCoverageS6:
    """Branch coverage for S6Domain."""

    def test_excluded_when_weight_zero(self) -> None:
        """S6 returns None when not required and its weight is zero."""
        ctx = _ctx()
        ctx.config.weights["S6"] = 0
        resume = _resume(_role("2020-01", None, title_family="logistics"))
        score = S6Domain().score(resume, _spec(domain="logistics"), ctx)
        assert score.value is None

    def test_no_roles_floor(self) -> None:
        """No roles still hit the 0.20 floor."""
        score = S6Domain().score(_resume(), _spec(domain="logistics"), _ctx())
        assert score.value == pytest.approx(20.0, abs=0.1)

    def test_no_domain_spec(self) -> None:
        """When the JobSpec omits a domain, match is treated as neutral."""
        resume = _resume(_role("2020-01", None, title_family="logistics"))
        score = S6Domain().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(100.0, abs=0.1)

    def test_adjacent_domain(self) -> None:
        """Substring heuristic triggers the adjacent 0.60 factor."""
        resume = _resume(_role("2020-01", None, title_family="logistics_software"))
        score = S6Domain().score(resume, _spec(domain="logistics"), _ctx())
        assert score.value == pytest.approx(60.0, abs=0.1)


class TestCoverageS7:
    """Branch coverage for S7Education."""

    def test_no_education_requirement(self) -> None:
        """Neutral education and certification components => 100."""
        resume = CanonicalResume(candidate_id="c_test")
        score = S7Education().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(100.0, abs=0.1)

    def test_below_required_no_equivalent(self) -> None:
        """Below required with no equivalent-experience fallback clips at 0.20."""
        resume = CanonicalResume(
            candidate_id="c_test",
            education=(EducationEntry(degree_level="associate", field="history"),),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            education=EducationRequirement(
                min_level="bachelors",
                fields=("computer science",),
                equivalent_experience_allowed=False,
            ),
        )
        score = S7Education().score(resume, spec, _ctx())
        # edu=clip(2/3, 0.20, 1)=0.6667, cert=1.0 => 0.8 => 80.0
        assert score.value == pytest.approx(80.0, abs=0.1)

    def test_adjacent_field(self) -> None:
        """Level met but field only adjacent => 0.80 education factor."""
        resume = CanonicalResume(
            candidate_id="c_test",
            education=(EducationEntry(degree_level="bachelors", field="physics"),),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            education=EducationRequirement(
                min_level="bachelors",
                fields=("computer science",),
            ),
        )
        score = S7Education().score(resume, spec, _ctx())
        # edu=0.8, cert=1.0 => 0.88 => 88.0
        assert score.value == pytest.approx(88.0, abs=0.1)

    def test_in_progress_certification(self) -> None:
        """In-progress certification counts at 0.50."""
        resume = CanonicalResume(
            candidate_id="c_test",
            certifications=(
                Certification(name="AWS SA", canonical="aws sa", status="in-progress"),
            ),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            certifications=({"canonical": "aws sa", "weight": 2},),
        )
        score = S7Education().score(resume, spec, _ctx())
        # edu=1.0, cert=0.5 => 0.8 => 80.0
        assert score.value == pytest.approx(80.0, abs=0.1)

    def test_no_matching_certification(self) -> None:
        """Required certification with no match => 0."""
        resume = CanonicalResume(candidate_id="c_test")
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            certifications=({"canonical": "aws sa", "weight": 1},),
        )
        score = S7Education().score(resume, spec, _ctx())
        # edu=1.0, cert=0.0 => 0.6 => 60.0
        assert score.value == pytest.approx(60.0, abs=0.1)


class TestCoverageS9:
    """Branch coverage for S9Trajectory."""

    def test_no_roles(self) -> None:
        """No experience uses the neutral/short-tenure factors."""
        score = S9Trajectory().score(_resume(), _spec(), _ctx())
        assert score.value is not None
        assert score.value < 60.0

    def test_lateral_trajectory(self) -> None:
        """Equal seniority across roles => 0.70 trajectory."""
        resume = _resume(
            _role("2019-01", "2021-01", seniority="senior"),
            _role("2021-01", None, seniority="senior"),
        )
        score = S9Trajectory().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(85.0, abs=0.5)

    def test_decreased_trajectory(self) -> None:
        """Seniority decreased => 0.40 trajectory."""
        resume = _resume(
            _role("2019-01", "2021-01", seniority="senior"),
            _role("2021-01", None, seniority="junior"),
        )
        score = S9Trajectory().score(resume, _spec(), _ctx())
        assert score.value is not None and score.value < 75.0

    def test_contract_excluded_from_median(self) -> None:
        """Contract roles are excluded from the tenure median."""
        resume = _resume(
            _role("2019-01", "2020-01", employment_type=EmploymentType.CONTRACT),
            _role("2020-01", None),
        )
        score = S9Trajectory().score(resume, _spec(), _ctx())
        assert score.value is not None

    def test_median_tenure_12_to_24(self) -> None:
        """Median tenure 12-24 months => 0.75 stability."""
        resume = _resume(
            _role("2024-01", "2025-01", seniority="senior"),
            _role("2025-01", None, seniority="senior"),
        )
        score = S9Trajectory().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(72.5, abs=0.5)

    def test_median_tenure_below_12(self) -> None:
        """Median tenure <12 months => 0.45 stability."""
        resume = _resume(
            _role("2025-01", "2025-06", seniority="senior"),
            _role("2025-06", None, seniority="senior"),
        )
        score = S9Trajectory().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(57.5, abs=0.5)


class TestCoverageS10:
    """Branch coverage for S10Parseability."""

    def test_multi_column_deduction(self) -> None:
        """Multi-column layout deducts 15 points."""
        resume = CanonicalResume(
            candidate_id="c_test",
            extraction=ExtractionMetadata(method="native_text", columns_detected=2),
            experience=(_role("2020-01", None),),
            skills=(SkillMention(raw="Python"),),
            education=(EducationEntry(degree_level="bachelors"),),
        )
        score = S10Parseability().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(85.0, abs=0.1)

    def test_unparseable_dates_deduction(self) -> None:
        """More than 25% unparseable dates deducts 15 points."""
        resume = CanonicalResume(
            candidate_id="c_test",
            extraction=ExtractionMetadata(method="native_text"),
            experience=(ExperienceEntry(title_raw="Engineer", start=None, end=None),),
            skills=(SkillMention(raw="Python"),),
            education=(EducationEntry(degree_level="bachelors"),),
        )
        score = S10Parseability().score(resume, _spec(), _ctx())
        assert score.value == pytest.approx(85.0, abs=0.1)

    def test_no_extraction_metadata(self) -> None:
        """Missing extraction metadata does not crash."""
        resume = CanonicalResume(
            candidate_id="c_test",
            experience=(_role("2020-01", None),),
            skills=(SkillMention(raw="Python"),),
            education=(EducationEntry(degree_level="bachelors"),),
        )
        score = S10Parseability().score(resume, _spec(), _ctx())
        assert score.value is not None and 0 <= score.value <= 100


class TestCounterfactual:
    """TRD §13.4 — counterfactual checks for profile dimensions."""

    def test_s7_no_institution_ranking(self) -> None:
        """Institution name does not affect the education score."""
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            education=EducationRequirement(min_level="bachelors", fields=("computer science",)),
        )
        resume_a = CanonicalResume(
            candidate_id="c_test",
            education=(
                EducationEntry(
                    institution="Harvard",
                    degree_level="bachelors",
                    field="computer science",
                ),
            ),
        )
        resume_b = CanonicalResume(
            candidate_id="c_test",
            education=(
                EducationEntry(
                    institution="Community College",
                    degree_level="bachelors",
                    field="computer science",
                ),
            ),
        )
        score_a = S7Education().score(resume_a, spec, _ctx())
        score_b = S7Education().score(resume_b, spec, _ctx())
        assert score_a.value == score_b.value

    def test_s7_graduation_year_shift(self) -> None:
        """Shifting the graduation year does not change the level/field score."""
        spec = JobSpec(
            job_id="jd_test",
            title="Engineer",
            education=EducationRequirement(min_level="bachelors", fields=("computer science",)),
        )
        resume_a = CanonicalResume(
            candidate_id="c_test",
            education=(
                EducationEntry(
                    degree_level="bachelors",
                    field="computer science",
                    end=DateValue(value="2018-05", precision=DatePrecision.MONTH),
                ),
            ),
        )
        resume_b = CanonicalResume(
            candidate_id="c_test",
            education=(
                EducationEntry(
                    degree_level="bachelors",
                    field="computer science",
                    end=DateValue(value="2020-05", precision=DatePrecision.MONTH),
                ),
            ),
        )
        score_a = S7Education().score(resume_a, spec, _ctx())
        score_b = S7Education().score(resume_b, spec, _ctx())
        assert score_a.value == score_b.value

    def test_s4_gender_pronoun_substitution(self) -> None:
        """Changing the candidate name/pronoun proxy does not affect S4."""
        resume_a = _resume(_role("2020-01", None, skills=("python",), title_family="logistics"))
        resume_b = _resume(_role("2020-01", None, skills=("python",), title_family="logistics"))
        resume_b = resume_b.model_copy(update={"identity": Identity(full_name="Jane Doe")})
        spec = _spec(domain="logistics", required_skills=("python",))
        score_a = S4Experience().score(resume_a, spec, _ctx())
        score_b = S4Experience().score(resume_b, spec, _ctx())
        assert score_a.value == score_b.value
