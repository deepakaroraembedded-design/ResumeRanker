from __future__ import annotations

from collections.abc import Sequence

from ats_scan.models.config import SelectionConfig
from ats_scan.models.scoring import ScoreCard


def select(cards: Sequence[ScoreCard], config: SelectionConfig) -> tuple[ScoreCard, ...]:
    """Mark candidates Selected according to TRD FR-802.

    A candidate is selected when they are eligible and satisfy the configured
    selection rule:

    - ``composite >= threshold`` (default 70.0), and optionally
    - ``rank <= top_n``.

    Candidates with no composite score or no rank cannot satisfy the matching
    part of the rule and are therefore not selected.
    """
    result: list[ScoreCard] = []
    for card in cards:
        composite = card.composite
        if composite is None:
            result.append(card.model_copy(update={"selected": False}))
            continue

        is_selected = card.eligible and composite >= config.threshold
        if is_selected and config.top_n is not None:
            is_selected = card.rank is not None and card.rank <= config.top_n
        result.append(card.model_copy(update={"selected": is_selected}))
    return tuple(result)
