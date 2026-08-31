from __future__ import annotations

from datetime import date, datetime
from statistics import median
from typing import ClassVar

from resume_ranker.models.jobspec import JobSpec
from resume_ranker.models.resume import (
    CanonicalResume,
    DatePrecision,
    EmploymentType,
    ExperienceEntry,
)
from resume_ranker.models.run import ScoringContext
from resume_ranker.models.scoring import SubScore
from resume_ranker.scoring.registry import dimension

_SENIORITY_ORDINALS: dict[str, int] = {
    "intern": 0,
    "entry": 1,
    "junior": 1,
    "associate": 2,
    "mid": 2,
    "senior": 3,
    "lead": 3,
    "staff": 4,
    "principal": 5,
    "director": 5,
    "vp": 6,
    "executive": 7,
    "c-level": 7,
}


@dimension
class S9Trajectory:
    """Career trajectory and stability (TRD §5.3.9)."""

    id: ClassVar[str] = "S9"
    name: ClassVar[str] = "Career trajectory and stability"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.9 — Career trajectory and stability.

        S9 = 100 * (0.5 * trajectory + 0.5 * stability). Employment gaps are
        detected and reported but are never penalised. Contract/freelance roles
        are excluded from the median tenure calculation.
        """
        now = date.fromisoformat(ctx.now)
        trajectory = _trajectory_component(resume, now)
        stability = _stability_component(resume, now)
        raw = 0.5 * trajectory + 0.5 * stability
        value = max(0.0, min(100.0, 100.0 * raw))

        return SubScore(
            dimension=self.id,
            value=round(value, 2),
            evidence=(),
            detail={"trajectory": round(trajectory, 4), "stability": round(stability, 4)},
        )


def _trajectory_component(resume: CanonicalResume, now: date) -> float:
    """Return the TRD §5.3.9 trajectory factor in [0, 1]."""
    window_start = now.replace(year=now.year - 6)
    recent_roles = [role for role in resume.experience if _role_end(role, now) >= window_start]

    if len(recent_roles) < 2:
        return 0.70

    sorted_roles = sorted(
        recent_roles,
        key=lambda role: _role_start(role, now) or date.min,
    )
    first_seniority = _seniority_ordinal(sorted_roles[0])
    last_seniority = _seniority_ordinal(sorted_roles[-1])

    if last_seniority > first_seniority:
        return 1.00
    if last_seniority == first_seniority:
        return 0.70
    return 0.40


def _stability_component(resume: CanonicalResume, now: date) -> float:
    """Return the TRD §5.3.9 stability factor in [0, 1]."""
    tenures: list[int] = []
    for role in resume.experience:
        if role.employment_type in (EmploymentType.CONTRACT, EmploymentType.FREELANCE):
            continue
        months = _role_months(role, now)
        if months is not None and months > 0:
            tenures.append(months)

    if not tenures:
        return 0.45

    med = int(median(tenures))
    if med >= 24:
        return 1.00
    if med >= 12:
        return 0.75
    return 0.45


def _role_start(role: ExperienceEntry, now: date) -> date | None:
    """Best-effort start date for a role."""
    return _resolve_date(role.start, now)


def _role_end(role: ExperienceEntry, now: date) -> date:
    """Best-effort end date for a role (defaults to now)."""
    return _resolve_date(role.end, now) or now


def _role_months(role: ExperienceEntry, now: date) -> int | None:
    """Return the number of months between a role's start and end dates."""
    start = _role_start(role, now)
    end = _role_end(role, now)
    if start is None or end < start:
        return None
    return (end.year - start.year) * 12 + (end.month - start.month)


def _seniority_ordinal(role: ExperienceEntry) -> int:
    """Map a role's seniority to an ordinal for trajectory comparison."""
    if role.seniority:
        return _SENIORITY_ORDINALS.get(role.seniority.lower().strip(), 2)
    if role.title_raw:
        lower = role.title_raw.lower()
        for token, level in _SENIORITY_ORDINALS.items():
            if token in lower:
                return level
    return 2


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
