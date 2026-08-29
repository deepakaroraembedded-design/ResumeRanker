from __future__ import annotations

import math
from datetime import date, datetime
from typing import ClassVar

from ats_scan.models.jobspec import JobSpec
from ats_scan.models.resume import CanonicalResume, DatePrecision, ExperienceEntry
from ats_scan.models.run import ScoringContext
from ats_scan.models.scoring import SubScore
from ats_scan.scoring.registry import dimension


@dimension
class S6Domain:
    """Domain and industry match (TRD §5.3.6)."""

    id: ClassVar[str] = "S6"
    name: ClassVar[str] = "Domain and industry match"
    requires: ClassVar[frozenset[str]] = frozenset()

    def score(self, resume: CanonicalResume, spec: JobSpec, ctx: ScoringContext) -> SubScore:
        """TRD §5.3.6 — Domain and industry match.

        S6 = 100 * max over roles of (domain_match * recency_weight). Domain match
        is exact sector = 1.0, adjacent = 0.60, no match = 0.20 (floor). The
        dimension is excluded when the JobSpec does not require a domain and the
        configured weight is 0.
        """
        weight = ctx.config.weights.get(self.id, 5)
        domain_required = bool(spec.domain and spec.domain.required)
        if weight == 0 and not domain_required:
            return SubScore(dimension=self.id, value=None, evidence=())

        now = date.fromisoformat(ctx.now)
        target_domain = spec.domain.industry.lower() if spec.domain else None

        best = 0.0
        for role in resume.experience:
            match = _domain_match(role, target_domain)
            recency = _recency_weight(role, now, half_life_years=6.0, floor=0.55)
            weighted = match * recency
            if weighted > best:
                best = weighted

        # Floor is 0.20, but if there are no roles the floor still applies.
        best = max(best, 0.20)
        return SubScore(
            dimension=self.id,
            value=round(100.0 * best, 2),
            evidence=(),
            detail={"best_domain_match": round(best, 4)},
        )


def _domain_match(role: ExperienceEntry, target_domain: str | None) -> float:
    """Return the TRD §5.3.6 domain match factor for a single role."""
    if target_domain is None:
        return 1.0
    role_domain = (role.title_family or role.title_raw or "").lower()
    if role_domain == target_domain:
        return 1.0
    # Adjacency is not modelled in the frozen title fields; treat as the floor.
    return 0.60 if _is_adjacent(role_domain, target_domain) else 0.20


def _is_adjacent(role_domain: str, target_domain: str) -> bool:
    """Adjacency heuristic: one is a substring of the other."""
    return role_domain in target_domain or target_domain in role_domain


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
