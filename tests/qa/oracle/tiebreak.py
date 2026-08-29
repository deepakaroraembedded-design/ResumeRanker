from __future__ import annotations

from typing import Any


def rank_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """TRD §5.6.  Deterministic tie-break chain applied to a list of candidates."""

    def key(c: dict[str, Any]) -> tuple[float, float, float, float, str]:
        composite = -float(c.get("composite", 0.0))
        s1 = -float(c.get("S1", 0.0))
        s4 = -float(c.get("S4", 0.0))
        confidence = -float(c.get("confidence", 0.0))
        candidate_id = str(c.get("candidate_id", ""))
        return (composite, s1, s4, confidence, candidate_id)

    return sorted(candidates, key=key)
