from __future__ import annotations

from collections.abc import Sequence

from resume_ranker.models.scoring import ScoreCard


def _sub_score_value(card: ScoreCard, dimension: str) -> float:
    """Return the value of a sub-score, or 0.0 if missing/unavailable."""
    sub = card.sub_scores.get(dimension)
    if sub is None:
        return 0.0
    return sub.value if sub.value is not None else 0.0


def rank(cards: Sequence[ScoreCard]) -> tuple[ScoreCard, ...]:
    """Return a deterministic, total ordering of *cards* per TRD §5.6.

    The tie-break chain is:

    1. Higher composite score.
    2. Higher S1 (required skills coverage).
    3. Higher S4 (relevant experience depth).
    4. Higher confidence.
    5. Lexicographic ``candidate_id`` (ascending).

    The ordering is input-order independent and never uses file order or
    timestamps. Each returned card has its ``rank`` field set to 1, 2, ...
    """

    def key(card: ScoreCard) -> tuple[float, float, float, float, str]:
        return (
            -(card.composite or 0.0),
            -_sub_score_value(card, "S1"),
            -_sub_score_value(card, "S4"),
            -(card.confidence or 0.0),
            card.candidate_id,
        )

    sorted_cards = sorted(cards, key=key)
    for i, card in enumerate(sorted_cards):
        card.rank = i + 1
    return tuple(sorted_cards)
