from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ats_scan.models.common import IntegrityFinding
from ats_scan.models.config import IntegrityConfig, ScoringConfig
from ats_scan.models.scoring import Band, SubScore
from ats_scan.scoring.bands import band


@dataclass(frozen=True)
class Aggregation:
    """The result of aggregating sub-scores into a composite score.

    Attributes match the fields that C-15 copies into a ``ScoreCard``.
    """

    base_score: float
    integrity_penalty: float
    composite: float
    band: Band
    flags: tuple[str, ...]
    reason_codes: tuple[str, ...]


def aggregate(
    sub_scores: Mapping[str, SubScore],
    weights: Mapping[str, float],
    findings: tuple[IntegrityFinding, ...],
    scoring_cfg: ScoringConfig,
    integrity_cfg: IntegrityConfig,
) -> Aggregation:
    """Compute the weighted composite score with integrity penalties.

    Implements the TRD §5.4 aggregation pipeline:

    1. Drop dimensions with weight 0 or unavailable value (``None``).
    2. Renormalise the remaining weights and compute the weighted mean.
    3. Add integrity penalties, capped at the configured total (default 25).
    4. Clip the composite to [0, 100] and assign a band.

    Penalties are always disclosed in ``flags`` and ``reason_codes``.
    """
    active: list[tuple[str, float, float]] = []
    for dimension, sub in sub_scores.items():
        weight = weights.get(dimension, 0.0)
        if weight > 0 and sub.value is not None:
            active.append((dimension, weight, sub.value))

    if not active:
        return Aggregation(
            base_score=0.0,
            integrity_penalty=0.0,
            composite=0.0,
            band=band(0.0, scoring_cfg.bands),
            flags=(),
            reason_codes=(),
        )

    total_weight = sum(weight for _, weight, _ in active)
    # Per-dimension weighted contribution rounded to 2 decimals to match the
    # published worked example in TRD §5.8 (sums exactly to 87.06).
    base = sum(round(weight * value / total_weight, 2) for _, weight, value in active)

    penalty_map = {k.lower(): v for k, v in integrity_cfg.penalties.items()}
    cap = float(integrity_cfg.penalty_total_cap)
    penalty = 0.0
    applied_codes: list[str] = []
    for finding in findings:
        code = finding.code.lower()
        if code in penalty_map:
            penalty += penalty_map[code]
            applied_codes.append(finding.code)

    penalty = round(min(penalty, cap), 2)
    composite = max(0.0, min(100.0, round(base - penalty, 2)))

    flags: list[str] = [f"PENALTY_APPLIED:{code}" for code in applied_codes]
    if penalty > 0:
        flags.append(f"PENALTY_TOTAL:{penalty}")

    return Aggregation(
        base_score=base,
        integrity_penalty=penalty,
        composite=composite,
        band=band(composite, scoring_cfg.bands),
        flags=tuple(flags),
        reason_codes=tuple(applied_codes),
    )
