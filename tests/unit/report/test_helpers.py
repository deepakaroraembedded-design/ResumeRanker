from __future__ import annotations

from ats_scan.models.scoring import ScoreCard, SubScore
from ats_scan.report._helpers import preferred_gate, required_gate


def test_required_gate_from_s1_detail() -> None:
    card = ScoreCard(
        candidate_id="c_test",
        job_id="j_test",
        run_id="r_test",
        confidence=None,
        sub_scores={
            "S1": SubScore(
                dimension="S1",
                value=75.0,
                detail={"gate": {"passed": 5, "total": 16}},
            ),
        },
    )
    assert required_gate(card) == "5/16"


def test_required_gate_missing_detail() -> None:
    card = ScoreCard(
        candidate_id="c_test",
        job_id="j_test",
        run_id="r_test",
        confidence=None,
    )
    assert required_gate(card) == ""


def test_preferred_gate_from_s2_detail() -> None:
    card = ScoreCard(
        candidate_id="c_test",
        job_id="j_test",
        run_id="r_test",
        confidence=None,
        sub_scores={
            "S2": SubScore(
                dimension="S2",
                value=60.0,
                detail={"gate": {"passed": 3, "total": 10}},
            ),
        },
    )
    assert preferred_gate(card) == "3/10"


def test_preferred_gate_skips_when_s2_unavailable() -> None:
    card = ScoreCard(
        candidate_id="c_test",
        job_id="j_test",
        run_id="r_test",
        confidence=None,
        sub_scores={
            "S2": SubScore(dimension="S2", value=None),
        },
    )
    assert preferred_gate(card) == ""
