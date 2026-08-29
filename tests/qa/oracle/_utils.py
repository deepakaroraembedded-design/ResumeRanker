from __future__ import annotations

import math
from datetime import date
from typing import Any


def clamp(value: float, low: float, high: float) -> float:
    """Clamp a value to a closed interval."""
    return min(max(value, low), high)


def parse_date(value: str | None) -> date | None:
    """Parse a partial ISO-8601 date string used in the canonical model.

    Supports ``YYYY``, ``YYYY-MM`` and ``YYYY-MM-DD``.  ``None`` and the
    special ``present`` precision are returned as ``None`` because the caller
    is expected to supply the actual end date.
    """
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"present", "now", ""}:
        return None
    parts = value.split("-")
    if len(parts) == 1 and parts[0].isdigit():
        return date(int(parts[0]), 1, 1)
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        return date(int(parts[0]), int(parts[1]), 1)
    if len(parts) == 3:
        return date(int(parts[0]), int(parts[1]), int(parts[2]))
    return None


def month_delta(start: date, end: date) -> int:
    """Return the whole-month delta between two dates."""
    return (end.year - start.year) * 12 + (end.month - start.month)


def years_between(start: date, end: date) -> float:
    """Approximate years between two dates as months / 12."""
    return month_delta(start, end) / 12.0


def recency_factor(
    last_used: str | date | None,
    now: date,
    half_life_years: float,
    floor: float,
) -> float:
    """TRD §5.3.1.  f_recency = clamp(exp(-ln(2) * dt / H), r_min, 1.0)."""
    if last_used is None:
        return floor
    parsed = parse_date(last_used) if isinstance(last_used, str) else last_used
    if parsed is None:
        return floor
    dt = years_between(parsed, now)
    if dt < 0:
        dt = 0.0
    return clamp(math.exp(-math.log(2) * dt / half_life_years), floor, 1.0)


def get_cfg(cfg: dict[str, Any] | None, *path: str, default: Any) -> Any:
    """Walk a nested dictionary with dotted-style keys, returning a default."""
    if cfg is None:
        return default
    current: Any = cfg
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current
