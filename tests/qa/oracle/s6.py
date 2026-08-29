from __future__ import annotations

from datetime import date
from typing import Any

from tests.qa.oracle._utils import recency_factor

DOMAIN_MATCH: dict[str, float] = {
    "exact": 1.00,
    "adjacent": 0.60,
    "none": 0.20,
}


def s6_domain(
    roles: list[dict[str, Any]],
    cfg: dict[str, Any],
    now: date,
) -> float:
    """TRD §5.3.6.  S6 = 100 * max over roles of domain_match weighted by recency."""
    if not roles:
        return 0.0

    best = 0.0
    for role in roles:
        match = role.get("domain_match", "none")
        match_value = DOMAIN_MATCH.get(match, 0.20) if isinstance(match, str) else float(match)
        rw = recency_factor(role.get("end"), now, 4.0, 0.50)
        value = match_value * rw
        if value > best:
            best = value
    return 100.0 * best
