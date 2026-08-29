from __future__ import annotations

from typing import Any

from tests.qa.oracle._utils import clamp, get_cfg


def s3_semantic(
    jd_chunks: list[dict[str, Any]],
    similarities: list[list[float]],
    pool_raw_scores: list[float],
    llm_rubric_score: float | None,
    cfg: dict[str, Any],
    deterministic: bool = False,
) -> float:
    """TRD §5.3.3.  Asymmetric max-similarity, pool calibration, LLM rubric blend.

    ``similarities[j][k]`` is the cosine between JD chunk ``j`` and resume
    chunk ``k``.  ``pool_raw_scores`` is the raw score for every candidate in
    the pool (including this one) and is used for percentile calibration.
    """
    if not jd_chunks:
        return 0.0

    weight_total = 0.0
    weighted_similarity = 0.0
    for j, chunk in enumerate(jd_chunks):
        weight = float(chunk.get("weight", 1.0))
        weight_total += weight
        best = max(similarities[j]) if j < len(similarities) and similarities[j] else 0.0
        weighted_similarity += weight * best

    if weight_total == 0:
        return 0.0
    raw = weighted_similarity / weight_total

    min_pool_size = get_cfg(cfg, "semantic", "pool_calibration_min_size", default=30)
    anchor_low = get_cfg(cfg, "semantic", "anchor_low", default=0.25)
    anchor_high = get_cfg(cfg, "semantic", "anchor_high", default=0.70)

    if len(pool_raw_scores) >= min_pool_size:
        sorted_scores = sorted(pool_raw_scores)
        p10 = sorted_scores[max(0, (len(sorted_scores) - 1) // 10)]
        p90 = sorted_scores[min(len(sorted_scores) - 1, 9 * (len(sorted_scores) - 1) // 10)]
        spread = max(p90 - p10, 0.05)
        cal = clamp((raw - p10) / spread, 0.0, 1.0)
    else:
        spread = max(anchor_high - anchor_low, 0.05)
        cal = clamp((raw - anchor_low) / spread, 0.0, 1.0)

    if deterministic or llm_rubric_score is None:
        return 100.0 * cal
    return 0.6 * (100.0 * cal) + 0.4 * llm_rubric_score
