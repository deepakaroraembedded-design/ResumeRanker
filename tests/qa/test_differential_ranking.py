from __future__ import annotations

from typing import Any

import pytest
from tests.qa import oracle


def _c(
    candidate_id: str,
    composite: float,
    s1: float,
    s4: float,
    confidence: float,
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id,
        "composite": composite,
        "S1": s1,
        "S4": s4,
        "confidence": confidence,
    }


@pytest.mark.slow
def test_oracle_ranking_is_deterministic() -> None:
    """Ranking oracle follows the TRD §5.6 tie-break chain."""
    candidates = [
        _c("c_low", 80.0, 90.0, 70.0, 0.9),
        _c("c_high", 85.0, 70.0, 80.0, 0.8),
        _c("c_tie_a", 80.0, 90.0, 70.0, 0.9),
        _c("c_tie_b", 80.0, 90.0, 70.0, 0.95),
    ]
    ranked = oracle.rank_candidates(candidates)
    ids = [c["candidate_id"] for c in ranked]
    assert ids == ["c_high", "c_tie_b", "c_low", "c_tie_a"]
