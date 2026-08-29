from __future__ import annotations

from datetime import date
from typing import Any

from tests.qa.oracle._utils import recency_factor


def s5_title(
    roles: list[dict[str, Any]],
    cfg: dict[str, Any],
    now: date,
) -> float:
    """TRD §5.3.5.  S5 = 100 * max over roles of title_sim * seniority_factor * rw(r)."""
    if not roles:
        return 0.0

    best = 0.0
    for role in roles:
        title_sim = float(role.get("title_sim", 0.0))
        seniority_factor = float(role.get("seniority_factor", 0.0))
        rw = recency_factor(role.get("end"), now, 6.0, 0.55)
        value = title_sim * seniority_factor * rw
        if value > best:
            best = value
    return 100.0 * best
