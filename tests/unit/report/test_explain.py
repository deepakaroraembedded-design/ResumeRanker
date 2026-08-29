from __future__ import annotations

from ats_scan.models.scoring import ScoreCard
from ats_scan.report.explain import format_explanation_text, format_score_derivation


def test_format_explanation_text(scorecard_one: ScoreCard) -> None:
    text = format_explanation_text(scorecard_one)
    assert text == scorecard_one.explanation


def test_format_explanation_text_caps_at_120_words(scorecard_one: ScoreCard) -> None:
    scorecard = scorecard_one.model_copy(
        update={"explanation": "word " * 150},
    )
    text = format_explanation_text(scorecard)
    assert len(text.split()) <= 121


def test_format_score_derivation(scorecard_one: ScoreCard) -> None:
    text = format_score_derivation(scorecard_one)
    assert "Candidate: c_abc123" in text
    assert "Composite: 87.06" in text
    assert "S1: 88.40" in text
    assert "python" in text
    assert "dbt" in text
