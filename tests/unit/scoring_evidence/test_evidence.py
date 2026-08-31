from __future__ import annotations

from datetime import date

import pytest
from tests.fakes import FakeOntology

from resume_ranker.models.config import ProficiencyFactors, ScoringConfig
from resume_ranker.models.jobspec import JobSpec, RequiredSkill
from resume_ranker.models.resume import (
    Bullet,
    CanonicalResume,
    DatePrecision,
    DateValue,
    ExperienceEntry,
    SkillMention,
)
from resume_ranker.models.run import ScoringContext
from resume_ranker.models.scoring import MatchRoute, SubScore
from resume_ranker.scoring.dimensions.s1_required_skills import S1RequiredSkills
from resume_ranker.scoring.dimensions.s2_preferred_skills import S2PreferredSkills
from resume_ranker.scoring.dimensions.s8_skill_recency import S8SkillRecency
from resume_ranker.scoring.evidence import (
    ProficiencyKind,
    f_match,
    f_prof,
    f_recency,
    score_skill_coverage,
    years_since,
)


def _context(now: str = "2026-08-29") -> ScoringContext:
    return ScoringContext(
        ontology=FakeOntology(),
        titles=None,  # type: ignore[arg-type]
        embeddings=None,
        llm=None,
        config=ScoringConfig(),
        now=now,
    )


class TestMatchFactor:
    """TRD §5.3.1 — f_match table."""

    def test_exact_alias_case_are_perfect(self) -> None:
        assert f_match(MatchRoute.EXACT) == 1.0
        assert f_match(MatchRoute.ALIAS) == 1.0
        assert f_match(MatchRoute.CASE) == 1.0

    def test_child_parent_fuzzy(self) -> None:
        assert f_match(MatchRoute.CHILD) == pytest.approx(0.90)
        assert f_match(MatchRoute.PARENT) == pytest.approx(0.70)
        assert f_match(MatchRoute.FUZZY) == pytest.approx(0.85)

    def test_embedding_interpolates(self) -> None:
        assert f_match(MatchRoute.EMBEDDING, cosine=0.82) == pytest.approx(0.60)
        assert f_match(MatchRoute.EMBEDDING, cosine=0.90) == pytest.approx(0.66)
        assert f_match(MatchRoute.EMBEDDING, cosine=1.0) == pytest.approx(0.735)

    def test_transferable_and_none(self) -> None:
        assert f_match(MatchRoute.TRANSFERABLE) == 0.50
        assert f_match(MatchRoute.NONE) == 0.0


class TestProficiencyFactor:
    """TRD §5.3.1 — f_prof table."""

    def test_proficiency_table(self) -> None:
        factors = ProficiencyFactors()
        assert f_prof(ProficiencyKind.APPLIED_LONG, factors) == 1.00
        assert f_prof(ProficiencyKind.APPLIED_SHORT, factors) == 0.85
        assert f_prof(ProficiencyKind.LISTED_CORROBORATED, factors) == 0.80
        assert f_prof(ProficiencyKind.LISTED_ONLY, factors) == 0.55
        assert f_prof(ProficiencyKind.INCIDENTAL, factors) == 0.40


class TestRecencyFactor:
    """TRD §5.3.1 — f_recency formula."""

    def test_recency_now_is_one(self) -> None:
        assert f_recency(0.0, 4.0, 0.50) == 1.0

    def test_recency_one_half_life(self) -> None:
        assert f_recency(4.0, 4.0, 0.50) == pytest.approx(0.5)

    def test_recency_clamped_at_floor(self) -> None:
        assert f_recency(100.0, 4.0, 0.50) == 0.50

    def test_recency_timeless_half_life(self) -> None:
        assert f_recency(12.0, 12.0, 0.50) == pytest.approx(0.5)


class TestYearsSince:
    """Month-level date difference for recency."""

    def test_same_month(self) -> None:
        assert years_since(date(2026, 8, 1), date(2026, 8, 29)) == 0.0

    def test_one_year(self) -> None:
        assert years_since(date(2025, 8, 1), date(2026, 8, 1)) == 1.0

    def test_future_is_zero(self) -> None:
        assert years_since(date(2027, 1, 1), date(2026, 1, 1)) == 0.0


class TestSkillCoverage:
    """Shared S1/S2 scoring logic."""

    def test_score_is_bounded_and_weighted(self) -> None:
        resume = CanonicalResume(
            candidate_id="c_test",
            skills=(SkillMention(raw="Python", canonical="python"),),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Role",
            required_skills=(RequiredSkill(canonical="python", weight=5),),
        )
        score, *_ = score_skill_coverage(resume, spec.required_skills, _context())
        assert 0.0 <= score <= 100.0

    def test_order_independence(self) -> None:
        resume = CanonicalResume(
            candidate_id="c_test",
            skills=(
                SkillMention(raw="Python", canonical="python"),
                SkillMention(raw="Spark", canonical="apache-spark"),
            ),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Role",
            required_skills=(
                RequiredSkill(canonical="python", weight=5),
                RequiredSkill(canonical="apache-spark", weight=3),
            ),
        )
        a, *_ = score_skill_coverage(resume, spec.required_skills, _context())
        reversed_skills = tuple(reversed(spec.required_skills))
        b, *_ = score_skill_coverage(resume, reversed_skills, _context())
        assert a == pytest.approx(b)

    def test_unmatched_skills_become_gaps(self) -> None:
        resume = CanonicalResume(
            candidate_id="c_test",
            skills=(SkillMention(raw="Python", canonical="python"),),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Role",
            required_skills=(
                RequiredSkill(canonical="python", weight=5),
                RequiredSkill(canonical="dbt", weight=2),
            ),
        )
        score, _, matches, gaps = score_skill_coverage(resume, spec.required_skills, _context())
        assert len(gaps) == 1
        assert gaps[0].criterion == "dbt"
        assert len(matches) == 1


class TestDimensions:
    """S1, S2 and S8 boundary behaviour."""

    def test_s1_no_required_skills_is_neutral(self) -> None:
        spec = JobSpec(job_id="jd_empty", title="Role", required_skills=())
        resume = CanonicalResume(candidate_id="c_empty")
        score = S1RequiredSkills().score(resume, spec, _context())
        assert isinstance(score, SubScore)
        assert score.value == 100.0

    def test_s2_no_preferred_skills_returns_none(self) -> None:
        spec = JobSpec(job_id="jd_empty", title="Role", preferred_skills=())
        resume = CanonicalResume(candidate_id="c_empty")
        score = S2PreferredSkills().score(resume, spec, _context())
        assert isinstance(score, SubScore)
        assert score.value is None

    def test_s8_no_required_skills_returns_none(self) -> None:
        spec = JobSpec(job_id="jd_empty", title="Role", required_skills=())
        resume = CanonicalResume(candidate_id="c_empty")
        score = S8SkillRecency().score(resume, spec, _context())
        assert isinstance(score, SubScore)
        assert score.value is None

    def test_s1_experience_corroboration(self) -> None:
        resume = CanonicalResume(
            candidate_id="c_test",
            experience=(
                ExperienceEntry(
                    employer="Acme",
                    title_raw="Engineer",
                    start=DateValue(value="2020-01", precision=DatePrecision.MONTH),
                    end=DateValue(value=None, precision=DatePrecision.PRESENT),
                    bullets=(Bullet(text="Built PySpark pipelines", span=(0, 28)),),
                    skills_evidenced=("python",),
                ),
            ),
        )
        spec = JobSpec(
            job_id="jd_test",
            title="Role",
            required_skills=(RequiredSkill(canonical="python", weight=5),),
        )
        score = S1RequiredSkills().score(resume, spec, _context())
        assert score.value == pytest.approx(80.0, abs=0.1)
