from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import ClassVar, cast

from ats_scan.models.config import OverqualificationConfig
from ats_scan.models.jobspec import ExperienceRequirement, JobSpec
from ats_scan.models.resume import CanonicalResume, DatePrecision, EmploymentType, ExperienceEntry
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.protocols import TitleTaxonomy
from ats_scan.scoring.registry import dimension


@dataclass(frozen=True)
class _Interval:
    """Inclusive month interval used for calendar-union coverage."""

    start_year: int
    start_month: int
    end_year: int
    end_month: int
    relevance: float
    internship_factor: float


@dimension
class S4Experience:
    """Relevant experience depth (TRD §5.3.4)."""

    id: ClassVar[str] = "S4"
    name: ClassVar[str] = "Relevant experience depth"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.4 — Relevant experience depth.

        The score is driven by calendar-union coverage weighted by per-role
        relevance(title, skills, domain). Overlapping concurrent roles are
        collapsed to a union, taking the maximum relevance for any covered
        month. Internships count at half duration unless the JobSpec says
        otherwise. The four-branch piecewise maps relevant years to a 0..100
        score; over-qualification decay is off by default.
        """
        titles = cast(TitleTaxonomy, ctx.titles)
        now = date.fromisoformat(ctx.now)
        req = spec.experience or ExperienceRequirement(min_years=0, target_years=0)
        a = req.min_years
        b = req.target_years or (a + ctx.config.experience.default_target_offset_years if a else 0)

        intervals = _build_intervals(resume, spec, ctx, titles, now, req)
        n = _relevant_years(intervals)
        raw_years = _raw_years(intervals)
        value = _s4_from_years(n, a, b, ctx.config.experience.overqualification)

        return SubScore(
            dimension=self.id,
            value=value,
            evidence=(),
            detail={"relevant_years": round(n, 2), "raw_years": round(raw_years, 2)},
        )


def _build_intervals(
    resume: CanonicalResume,
    spec: JobSpec,
    ctx: ScoringContext,
    titles: TitleTaxonomy,
    now: date,
    req: ExperienceRequirement,
) -> tuple[_Interval, ...]:
    """Convert each experience role into a coverage interval with relevance."""
    intervals: list[_Interval] = []
    target_title = spec.title
    target_domain = spec.domain.industry.lower() if spec.domain else None

    for role in resume.experience:
        start = _resolve_date(role.start, now)
        end = _resolve_date(role.end, now)
        if start is None or end is None or end < start:
            continue

        title_sim = _title_similarity(role, target_title, titles)
        skill_overlap = _skill_overlap(role, spec)
        domain_sim = _domain_similarity(role, target_domain)
        relevance = max(0.0, min(1.0, 0.35 * title_sim + 0.45 * skill_overlap + 0.20 * domain_sim))

        factor = 1.0
        if role.employment_type == EmploymentType.INTERNSHIP and not req.count_internships:
            factor = ctx.config.experience.internship_duration_factor

        intervals.append(
            _Interval(
                start_year=start.year,
                start_month=start.month,
                end_year=end.year,
                end_month=end.month,
                relevance=relevance,
                internship_factor=factor,
            )
        )
    return tuple(intervals)


def _relevant_years(intervals: tuple[_Interval, ...]) -> float:
    """Calendar-union coverage with the maximum relevance per covered month."""
    if not intervals:
        return 0.0

    month_relevance: dict[int, float] = {}
    for interval in intervals:
        key_start = interval.start_year * 12 + interval.start_month
        key_end = interval.end_year * 12 + interval.end_month
        for key in range(key_start, key_end + 1):
            weighted = interval.relevance * interval.internship_factor
            month_relevance[key] = max(month_relevance.get(key, 0.0), weighted)

    return sum(month_relevance.values()) / 12.0


def _raw_years(intervals: tuple[_Interval, ...]) -> float:
    """Unweighted calendar-union years (for diagnostics)."""
    if not intervals:
        return 0.0
    covered: set[int] = set()
    for interval in intervals:
        key_start = interval.start_year * 12 + interval.start_month
        key_end = interval.end_year * 12 + interval.end_month
        covered.update(range(key_start, key_end + 1))
    return len(covered) / 12.0


def _s4_from_years(n: float, a: int, b: int, overqual: OverqualificationConfig) -> float:
    """TRD §5.3.4 piecewise mapping from relevant years to a 0..100 score."""
    # Guard a == 0: the JobSpec did not state a minimum, so the score is
    # neutral rather than dividing by zero.
    if a == 0:
        return 70.0

    if b == 0:
        b = a

    half_a = 0.5 * a

    if n < half_a:
        return 40.0 * (n / half_a)
    if n < a:
        return 40.0 + 30.0 * (n - half_a) / half_a
    if n <= b:
        if b == a:
            return 100.0
        return 70.0 + 30.0 * (n - a) / (b - a)

    # n > b
    if overqual.enabled:
        decay = min(overqual.cap, overqual.points_per_year * (n - b))
        return max(0.0, 100.0 - decay)
    return 100.0


def _title_similarity(
    role: ExperienceEntry, target_title: str | None, titles: TitleTaxonomy
) -> float:
    """Title similarity for this role using the title taxonomy."""
    if not role.title_raw or not target_title:
        return 0.0
    role_match = titles.normalise(role.title_raw)
    target_match = titles.normalise(target_title)
    if role_match is None or target_match is None:
        return 0.0
    return titles.similarity(role_match, target_match)


def _skill_overlap(role: ExperienceEntry, spec: JobSpec) -> float:
    """Fraction of required skills evidenced in this role."""
    required = {skill.canonical.lower() for skill in spec.required_skills}
    if not required:
        return 1.0
    evidenced = {skill.lower() for skill in role.skills_evidenced}
    if not evidenced:
        return 0.0
    matched = required & evidenced
    return len(matched) / len(required)


def _domain_similarity(role: ExperienceEntry, target_domain: str | None) -> float:
    """Domain similarity for this role.

    The frozen CanonicalResume model does not carry a per-role industry code,
    so the role's title_family is used as the best available proxy. When the
    JobSpec does not specify a domain the term is neutral (1.0).
    """
    if target_domain is None:
        return 1.0
    role_domain = (role.title_family or role.title_raw or "").lower()
    if role_domain == target_domain:
        return 1.0
    return 0.20


def _resolve_date(value: object | None, now: date) -> date | None:
    """Resolve a DateValue or present sentinel into a calendar date."""
    if value is None:
        return None
    precision = getattr(value, "precision", None)
    if precision == DatePrecision.PRESENT:
        return now
    raw = getattr(value, "value", None)
    if raw is None:
        return None
    if isinstance(raw, str):
        if len(raw) == 7:  # YYYY-MM
            try:
                return datetime.strptime(raw, "%Y-%m").date()
            except ValueError:
                return None
        if len(raw) == 4:  # YYYY
            try:
                return date(int(raw), 1, 1)
            except ValueError:
                return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    if isinstance(raw, date):
        return raw
    return None
