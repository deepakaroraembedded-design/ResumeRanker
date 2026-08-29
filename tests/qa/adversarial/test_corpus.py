from __future__ import annotations

import json
from pathlib import Path

import pytest

CORPUS = Path(__file__).parent.parent / "corpus" / "adversarial" / "cases.json"


@pytest.mark.slow
@pytest.mark.parametrize("case", json.loads(CORPUS.read_text(encoding="utf-8")))
def test_adversarial_corpus_case_has_expected_record(case: dict) -> None:
    """Q-ADV harness: every case declares expected flags and a score-movement bound."""
    assert "id" in case
    assert "expected_flags" in case and case["expected_flags"]
    assert "max_score_movement" in case
