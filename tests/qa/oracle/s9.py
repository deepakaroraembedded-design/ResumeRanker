from __future__ import annotations

from datetime import date
from typing import Any

from tests.qa.oracle._utils import month_delta, parse_date, years_between

SENIORITY_ORDINAL: dict[str, int] = {
    "intern": 0,
    "junior": 1,
    "mid": 2,
    "senior": 3,
    "staff": 4,
    "principal": 5,
    "executive": 6,
}


def _seniority(value: str | None) -> int:
    if value is None:
        return -1
    lowered = value.lower().strip()
    # Strip common qualifiers.
    for suffix in (" i", " ii", " iii", " iv", " v"):
        if lowered.endswith(suffix):
            lowered = lowered[: -len(suffix)].strip()
    if lowered in SENIORITY_ORDINAL:
        return SENIORITY_ORDINAL[lowered]
    for key, ordinal in SENIORITY_ORDINAL.items():
        if key in lowered:
            return ordinal
    return -1


def _role_months(role: dict[str, Any], now: date) -> int:
    if "months" in role and role["months"] is not None:
        return int(role["months"])
    start = (
        parse_date(role.get("start")) if isinstance(role.get("start"), str) else role.get("start")
    )
    end_raw = role.get("end")
    if end_raw is None or (isinstance(end_raw, str) and end_raw.lower() == "present"):
        end = now
    elif isinstance(end_raw, str):
        end = parse_date(end_raw) or now
    else:
        end = end_raw
    if start is None or end is None or end < start:
        return 0
    return max(0, month_delta(start, end))


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    n = len(sorted_values)
    if n % 2 == 1:
        return sorted_values[n // 2]
    return (sorted_values[n // 2 - 1] + sorted_values[n // 2]) / 2.0


def s9_trajectory(
    roles: list[dict[str, Any]],
    timeline: dict[str, Any] | None,
    cfg: dict[str, Any],
    now: date,
) -> float:
    """TRD §5.3.9.  S9 = 100 * (0.5 * trajectory + 0.5 * stability)."""
    recent_roles: list[dict[str, Any]] = []
    for role in roles:
        end_raw = role.get("end")
        if end_raw is None or (isinstance(end_raw, str) and end_raw.lower() == "present"):
            end = now
        elif isinstance(end_raw, str):
            end = parse_date(end_raw) or now
        else:
            end = end_raw
        if end is not None and years_between(end, now) <= 6.0:
            recent_roles.append(role)

    if len(recent_roles) < 2:
        trajectory = 0.70
    else:
        ordinals = [_seniority(r.get("seniority")) for r in recent_roles]
        ordinals = [o for o in ordinals if o >= 0]
        if len(ordinals) < 2:
            trajectory = 0.70
        else:
            first, last = ordinals[0], ordinals[-1]
            if last > first:
                trajectory = 1.00
            elif last < first:
                trajectory = 0.40
            else:
                trajectory = 0.70

    if timeline and timeline.get("median_tenure_months") is not None:
        median_tenure = float(timeline["median_tenure_months"])
    else:
        tenures = [
            float(_role_months(r, now))
            for r in roles
            if r.get("employment_type") not in {"contract", "freelance"}
        ]
        median_tenure = _median(tenures)

    if median_tenure >= 24:
        stability = 1.00
    elif median_tenure >= 12:
        stability = 0.75
    else:
        stability = 0.45

    return 100.0 * (0.5 * trajectory + 0.5 * stability)
