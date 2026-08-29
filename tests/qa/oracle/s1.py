from __future__ import annotations

from datetime import date
from typing import Any

from tests.qa.oracle._utils import clamp, get_cfg, recency_factor

MATCH_FACTOR: dict[str, float] = {
    "exact": 1.00,
    "canonical": 1.00,
    "alias": 1.00,
    "child": 0.90,
    "parent": 0.70,
    "transferable": 0.50,
    "none": 0.00,
}

PROF_FACTOR: dict[str, float] = {
    "applied_long": 1.00,
    "applied_short": 0.85,
    "listed_corroborated": 0.80,
    "listed_only": 0.55,
    "incidental": 0.40,
}


def _match_factor(evidence: dict[str, Any]) -> float:
    """Return f_match for a single evidence record."""
    if "f_match" in evidence:
        return float(evidence["f_match"])
    route = evidence.get("route", "none")
    if route == "fuzzy":
        ratio = float(evidence.get("ratio", 0.0))
        return 0.85 if ratio >= 92 else 0.00
    if route == "embedding":
        cosine = float(evidence.get("cosine", 0.0))
        if cosine < 0.82:
            return 0.00
        return clamp(0.60 + 0.75 * (cosine - 0.82), 0.00, 0.85)
    return MATCH_FACTOR.get(route, 0.00)


def _prof_factor(evidence: dict[str, Any]) -> float:
    """Return f_prof for a single evidence record."""
    if "f_prof" in evidence:
        return float(evidence["f_prof"])
    return PROF_FACTOR.get(evidence.get("proficiency", "none"), 0.00)


def s1_required_skills(
    required: list[dict[str, Any]],
    evidence: dict[str, list[dict[str, Any]]],
    cfg: dict[str, Any],
    now: date,
) -> float:
    """TRD §5.3.1.  S1 = 100 * SUM(w_i * m_i) / SUM(w_i).

    m_i = max over evidence e of f_match(e) * f_prof(e) * f_recency(e).
    """
    half_life = get_cfg(cfg, "recency", "half_life_years", default=4.0)
    half_life_timeless = get_cfg(cfg, "recency", "half_life_timeless_years", default=12.0)
    recency_floor = get_cfg(cfg, "recency", "floor", default=0.50)

    weighted_sum = 0.0
    weight_total = 0.0
    for skill in required:
        weight = float(skill["weight"])
        weight_total += weight
        best_m = 0.0
        skill_key = skill["canonical"]
        for ev in evidence.get(skill_key, ()):
            f_match = _match_factor(ev)
            f_prof = _prof_factor(ev)
            h = half_life_timeless if skill.get("timeless") else half_life
            last_used = ev.get("last_used")
            f_recency = recency_factor(last_used, now, h, recency_floor)
            m = f_match * f_prof * f_recency
            if m > best_m:
                best_m = m
        weighted_sum += weight * best_m

    if weight_total == 0:
        return 100.0
    return 100.0 * weighted_sum / weight_total
