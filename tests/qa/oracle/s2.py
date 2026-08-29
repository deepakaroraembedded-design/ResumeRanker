from __future__ import annotations

from datetime import date
from typing import Any

from tests.qa.oracle._utils import get_cfg, recency_factor
from tests.qa.oracle.s1 import _match_factor, _prof_factor


def s2_preferred_skills(
    preferred: list[dict[str, Any]],
    evidence: dict[str, list[dict[str, Any]]],
    cfg: dict[str, Any],
    now: date,
) -> float:
    """TRD §5.3.2.  S2 = 100 * SUM(v_j * m_j) / SUM(v_j), same m as S1."""
    half_life = get_cfg(cfg, "recency", "half_life_years", default=4.0)
    half_life_timeless = get_cfg(cfg, "recency", "half_life_timeless_years", default=12.0)
    recency_floor = get_cfg(cfg, "recency", "floor", default=0.50)

    weighted_sum = 0.0
    weight_total = 0.0
    for skill in preferred:
        weight = float(skill["weight"])
        skill_key = skill["canonical"]
        skill_evidence = evidence.get(skill_key, ())
        if not skill_evidence:
            continue
        weight_total += weight
        best_m = 0.0
        for ev in skill_evidence:
            f_match = _match_factor(ev)
            f_prof = _prof_factor(ev)
            h = half_life_timeless if skill.get("timeless") else half_life
            f_recency = recency_factor(ev.get("last_used"), now, h, recency_floor)
            m = f_match * f_prof * f_recency
            if m > best_m:
                best_m = m
        weighted_sum += weight * best_m

    if weight_total == 0:
        return 100.0
    return 100.0 * weighted_sum / weight_total
