from __future__ import annotations

from datetime import date
from typing import Any

from tests.qa.oracle._utils import clamp, get_cfg, parse_date


def _to_month(d: date) -> int:
    """Return an absolute month index for sweep-line computations."""
    return d.year * 12 + (d.month - 1)


def _parse_end(value: str | date | None, now: date) -> date:
    if value is None:
        return now
    if isinstance(value, date):
        return value
    parsed = parse_date(value)
    return parsed if parsed is not None else now


def _parse_start(value: str | date | None) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    return parse_date(value)


def _relevant_years(
    roles: list[dict[str, Any]],
    count_internships: bool,
    internship_factor: float,
    now: date,
) -> float:
    """TRD §5.3.4.  Calendar union of intervals weighted by max relevance."""
    intervals: list[tuple[int, int, float]] = []
    for role in roles:
        start = _parse_start(role.get("start"))
        end = _parse_end(role.get("end"), now)
        if start is None or end is None or end < start:
            continue
        start_m = _to_month(start)
        end_m = _to_month(end)
        relevance = clamp(
            0.35 * float(role.get("title_sim", 0.0))
            + 0.45 * float(role.get("skill_overlap", 0.0))
            + 0.20 * float(role.get("domain_sim", 0.0)),
            0.0,
            1.0,
        )
        if role.get("employment_type") == "internship" and not count_internships:
            months = max(0, end_m - start_m) * internship_factor
            end_m = start_m + int(months)
        if end_m > start_m:
            intervals.append((start_m, end_m, relevance))

    if not intervals:
        return 0.0

    # Sweep line: collect unique event points and compute max relevance per segment.
    points = sorted({p for i in intervals for p in (i[0], i[1])})
    total = 0.0
    for a_idx, b_idx in zip(points[:-1], points[1:], strict=False):
        if b_idx <= a_idx:
            continue
        best = 0.0
        for start_m, end_m, relevance in intervals:
            if start_m <= a_idx and end_m >= b_idx and relevance > best:
                best = relevance
        total += (b_idx - a_idx) / 12.0 * best
    return total


def s4_experience(
    roles: list[dict[str, Any]],
    requirement: dict[str, Any],
    cfg: dict[str, Any],
    now: date,
) -> float:
    """TRD §5.3.4.  Relevant experience depth from calendar-union coverage."""
    a = float(requirement.get("min_years", 0.0))
    offset = get_cfg(cfg, "experience", "default_target_offset_years", default=3)
    b = float(requirement.get("target_years", a + offset))

    count_internships = get_cfg(cfg, "experience", "count_internships", default=False)
    internship_factor = get_cfg(cfg, "experience", "internship_duration_factor", default=0.5)

    n = _relevant_years(roles, count_internships, internship_factor, now)

    overqual = get_cfg(cfg, "experience", "overqualification", default={})
    enabled = overqual.get("enabled", False) if isinstance(overqual, dict) else False
    overqual_cap = float(overqual.get("cap", 0)) if isinstance(overqual, dict) else 0.0
    points_per_year = (
        float(overqual.get("points_per_year", 3)) if isinstance(overqual, dict) else 3.0
    )

    if n < 0.5 * a:
        if a == 0:
            return 0.0
        return 40.0 * (n / (0.5 * a))
    if n < a:
        return 40.0 + 30.0 * (n - 0.5 * a) / (0.5 * a)
    if n <= b:
        if b == a:
            return 100.0
        return 70.0 + 30.0 * (n - a) / (b - a)
    if enabled and overqual_cap > 0:
        return 100.0 - min(overqual_cap, points_per_year * (n - b))
    return 100.0
