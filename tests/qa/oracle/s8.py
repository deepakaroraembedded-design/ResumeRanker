from __future__ import annotations

from datetime import date
from typing import Any

from tests.qa.oracle._utils import get_cfg, recency_factor


def s8_skill_recency(
    required: list[dict[str, Any]],
    evidence: dict[str, list[dict[str, Any]]],
    cfg: dict[str, Any],
    now: date,
) -> float:
    """TRD §5.3.8.  S8 = 100 * mean f_recency over top 3 weighted required skills."""
    if not required:
        return 100.0

    half_life = get_cfg(cfg, "recency", "half_life_years", default=4.0)
    half_life_timeless = get_cfg(cfg, "recency", "half_life_timeless_years", default=12.0)
    recency_floor = get_cfg(cfg, "recency", "floor", default=0.50)

    # Top 3 by weight, ties broken by canonical name for determinism.
    sorted_skills = sorted(
        required,
        key=lambda s: (-int(s["weight"]), s["canonical"]),
    )[:3]

    total = 0.0
    for skill in sorted_skills:
        skill_key = skill["canonical"]
        events = evidence.get(skill_key, ())
        if not events:
            total += recency_floor
            continue
        # Most recent evidenced use among all evidence records.
        last_used = None
        for ev in events:
            candidate = ev.get("last_used")
            if candidate is not None and (last_used is None or candidate > last_used):
                last_used = candidate
        h = half_life_timeless if skill.get("timeless") else half_life
        total += recency_factor(last_used, now, h, recency_floor)

    return 100.0 * (total / len(sorted_skills))
