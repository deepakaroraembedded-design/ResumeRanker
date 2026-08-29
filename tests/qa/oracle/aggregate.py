from __future__ import annotations

from typing import Any

from tests.qa.oracle._utils import clamp, get_cfg


def aggregate(
    sub_scores: dict[str, float | None],
    weights: dict[str, int],
    penalties: dict[str, float],
    cfg: dict[str, Any],
) -> dict[str, float]:
    """TRD §5.4.  Weighted mean of active dimensions, then integrity penalties."""
    active_weight = 0.0
    weighted_sum = 0.0
    for dim, value in sub_scores.items():
        weight = weights.get(dim, 0)
        if value is not None and weight > 0:
            weighted_sum += weight * value
            active_weight += weight

    base = 0.0 if active_weight == 0 else weighted_sum / active_weight

    cap = get_cfg(cfg, "integrity", "penalty_total_cap", default=25.0)
    total_penalty = clamp(sum(penalties.values()), 0.0, cap)
    composite = clamp(base - total_penalty, 0.0, 100.0)

    return {
        "base_score": base,
        "integrity_penalty": total_penalty,
        "composite": composite,
    }
