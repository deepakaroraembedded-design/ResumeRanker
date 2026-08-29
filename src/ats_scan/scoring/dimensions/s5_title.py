from __future__ import annotations

import math
from datetime import date
from typing import ClassVar, cast

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.ontology import TitleMatch
from ats_scan.models.resume import CanonicalResume, DatePrecision, ExperienceEntry
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.protocols import TitleTaxonomy
from ats_scan.scoring.registry import dimension


@dimension
class S5Title:
    """Role and title alignment (TRD §5.3.5)."""

    id: ClassVar[str] = "S5"
    name: ClassVar[str] = "Role and title alignment"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.5 — Role and title alignment.

        S5 = 100 * max over roles of title_sim * seniority_factor * recency_weight.
        Title similarity comes from the title taxonomy. Seniority factor maps the
        seniority gap to the TRD table. Recency uses a 6-year half-life and a 0.55
        floor.
        """
        titles = cast(TitleTaxonomy, ctx.titles)
        now = date.fromisoformat(ctx.now)
        target_match: TitleMatch | None = titles.normalise(spec.title) if spec.title else None

        best = 0.0
        for role in resume.experience:
            role_score = _role_alignment(role, titles, target_match, now)
            if role_score > best:
                best = role_score

        return SubScore(
            dimension=self.id,
            value=round(100.0 * best, 2),
            evidence=(),
            detail={"best_role_score": round(best, 4)},
        )


def _role_alignment(
    role: ExperienceEntry, titles: TitleTaxonomy, target_match: TitleMatch | None, now: date
) -> float:
    """Alignment score for a single role in [0, 1]."""
    if target_match is None or not role.title_raw:
        return 0.0

    role_match = titles.normalise(role.title_raw)
    if role_match is None:
        return 0.0

    title_sim = titles.similarity(role_match, target_match)
    seniority_gap = titles.seniority_gap(role_match, target_match)
    seniority_factor = _seniority_factor(seniority_gap)
    recency = _recency_weight(role, now, half_life_years=6.0, floor=0.55)
    return title_sim * seniority_factor * recency


def _seniority_factor(gap: int) -> float:
    """Map seniority gap (role - target) to the TRD §5.3.5 factor table."""
    if gap <= -3:
        return 0.45
    if gap == -2:
        return 0.70
    if gap in (-1, 0):
        return 1.00
    if gap == 1:
        return 0.95
    return 0.85


def _recency_weight(
    role: ExperienceEntry, now: date, half_life_years: float, floor: float
) -> float:
    """TRD §5.3.1 recency factor: clamp(exp(-ln2 * dt / H), floor, 1.0)."""
    end = _resolve_date(role.end, now)
    if end is None:
        return 1.0

    dt_days = (now - end).days
    dt_years = dt_days / 365.2425
    if dt_years <= 0.0:
        return 1.0

    return max(floor, math.exp(-math.log(2) * dt_years / half_life_years))


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
            from datetime import datetime

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
