from __future__ import annotations

import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ats_scan.fairness.impact import (
    compute_adverse_impact_report,
)
from ats_scan.models.scoring import ScoreCard, SubScore


def _card(
    candidate_id: str,
    composite: float,
    selected: bool | None = None,
    **sub_scores: float,
) -> ScoreCard:
    """Build a ScoreCard with the given sub-scores."""
    if selected is None:
        selected = composite >= 70.0
    return ScoreCard(
        candidate_id=candidate_id,
        job_id="job_test",
        run_id="run_test",
        composite=composite,
        selected=selected,
        sub_scores={dim: SubScore(dimension=dim, value=value) for dim, value in sub_scores.items()},
    )


@pytest.mark.parametrize(
    ("selected", "total", "expected"),
    [
        (1, 4, 0.25),
        (0, 4, 0.0),
        (4, 4, 1.0),
    ],
)
def test_selection_rate(selected, total, expected) -> None:
    """selection_rate is selected / total, with a safe zero-total guard."""
    cards = [_card(f"c{i}", 75.0, selected=i < selected, S1=75.0) for i in range(total)]
    demographics = {f"c{i}": "A" for i in range(total)}
    report = compute_adverse_impact_report(cards, demographics, weights={"S1": 100.0})
    group = report.groups[0]
    assert group.candidates == total
    assert group.selected == selected
    assert group.selection_rate == expected


def test_selection_rate_zero_total() -> None:
    """A group with no candidates is omitted from the report."""
    report = compute_adverse_impact_report([], {}, weights={"S1": 100.0})
    assert report.groups == ()


def test_impact_report_basic_statistics() -> None:
    """A small cohort yields correct selection rates, impact ratios, and warnings."""
    cards = [
        _card("c1", 75.0, S1=80.0, S2=70.0),
        _card("c2", 80.0, S1=85.0, S2=75.0),
        _card("c3", 65.0, S1=60.0, S2=70.0),
        _card("c4", 73.0, S1=75.0, S2=70.0),
        _card("c5", 71.0, S1=65.0, S2=70.0),
        _card("c6", 79.0, S1=80.0, S2=75.0),
    ]
    demographics = {
        "c1": "A",
        "c2": "A",
        "c3": "A",
        "c4": "B",
        "c5": "B",
        "c6": "B",
    }
    weights = {"S1": 50.0, "S2": 50.0}

    report = compute_adverse_impact_report(cards, demographics, weights=weights, threshold=70.0)

    assert report.reference_group == "B"
    assert report.dimensions == ("S1", "S2")

    group_a = next(g for g in report.groups if g.group == "A")
    group_b = next(g for g in report.groups if g.group == "B")

    assert group_a.candidates == 3
    assert group_a.selected == 2
    assert group_a.selection_rate == 2.0 / 3.0
    assert group_b.candidates == 3
    assert group_b.selected == 3
    assert group_b.selection_rate == 1.0
    assert group_a.impact_ratio == pytest.approx(2.0 / 3.0)

    assert group_a.small_sample_warning is True
    assert group_b.small_sample_warning is True

    assert group_a.mean_composite == pytest.approx((75.0 + 80.0 + 65.0) / 3.0)
    assert group_b.mean_composite == pytest.approx((73.0 + 71.0 + 79.0) / 3.0)

    assert group_a.mean_sub_scores["S1"] == pytest.approx((80.0 + 85.0 + 60.0) / 3.0)
    assert group_a.mean_sub_scores["S2"] == pytest.approx((70.0 + 75.0 + 70.0) / 3.0)


def test_leave_one_out_composite() -> None:
    """Leave-one-out composites are recomputed by redistributing weights."""
    cards = [
        _card("c1", 75.0, S1=80.0, S2=70.0),
        _card("c2", 80.0, S1=85.0, S2=75.0),
    ]
    demographics = {"c1": "A", "c2": "A"}
    weights = {"S1": 50.0, "S2": 50.0}

    report = compute_adverse_impact_report(cards, demographics, weights=weights)
    group = report.groups[0]

    # Without S1, only S2 remains with weight 50 -> mean equals S2.
    assert group.leave_one_out_composite["S1"] == pytest.approx((70.0 + 75.0) / 2.0)
    # Without S2, only S1 remains.
    assert group.leave_one_out_composite["S2"] == pytest.approx((80.0 + 85.0) / 2.0)


def test_small_sample_warning_threshold() -> None:
    """Groups with fewer than 30 candidates are flagged; groups with >= 30 are not."""
    cards = [_card(f"c{i}", 70.0, S1=70.0) for i in range(30)]
    demographics = {f"c{i}": "A" for i in range(30)}
    report = compute_adverse_impact_report(cards, demographics, weights={"S1": 100.0})
    assert not report.groups[0].small_sample_warning


def test_reference_group_override() -> None:
    """A supplied reference group is used even if it does not have the highest rate."""
    cards = [
        _card("c1", 80.0, S1=80.0),
        _card("c2", 60.0, S1=60.0),
    ]
    demographics = {"c1": "A", "c2": "B"}
    report = compute_adverse_impact_report(
        cards, demographics, weights={"S1": 100.0}, reference_group="B"
    )
    assert report.reference_group == "B"


def test_threshold_based_selection() -> None:
    """When threshold is supplied, selection is based on composite >= threshold."""
    cards = [
        _card("c1", 70.0, S1=70.0),
        _card("c2", 69.0, S1=69.0),
    ]
    demographics = {"c1": "A", "c2": "A"}
    report = compute_adverse_impact_report(
        cards, demographics, weights={"S1": 100.0}, threshold=70.0
    )
    group = report.groups[0]
    assert group.selected == 1
    assert group.selection_rate == 0.5


def test_scorecard_selected_flag() -> None:
    """When no threshold is supplied, ScoreCard.selected drives selection."""
    cards = [
        _card("c1", 70.0, selected=True, S1=70.0),
        _card("c2", 80.0, selected=False, S1=80.0),
    ]
    demographics = {"c1": "A", "c2": "A"}
    report = compute_adverse_impact_report(cards, demographics, weights={"S1": 100.0})
    group = report.groups[0]
    assert group.selected == 1


def test_empty_demographics() -> None:
    """A demographics mapping with no matching candidate yields an empty report."""
    cards = [_card("c1", 70.0, S1=70.0)]
    report = compute_adverse_impact_report(cards, {}, weights={"S1": 100.0})
    assert report.groups == ()
    assert report.reference_group is None


def test_equal_selection_rates_have_unit_impact_ratio() -> None:
    """Groups with identical selection rates have an impact ratio of 1.0."""
    cards = [
        _card("c1", 80.0, S1=80.0),
        _card("c2", 80.0, S1=80.0),
        _card("c3", 80.0, S1=80.0),
        _card("c4", 80.0, S1=80.0),
    ]
    demographics = {"c1": "A", "c2": "A", "c3": "B", "c4": "B"}
    report = compute_adverse_impact_report(cards, demographics, weights={"S1": 100.0})
    group_a = next(g for g in report.groups if g.group == "A")
    group_b = next(g for g in report.groups if g.group == "B")
    assert group_a.selection_rate == 1.0
    assert group_b.selection_rate == 1.0
    assert group_a.impact_ratio == 1.0
    assert group_b.impact_ratio == 1.0


def test_fisher_p_value_and_ci_bounds() -> None:
    """Fisher exact p-value and CI are bounded and coherent."""
    cards = [
        _card("c1", 80.0, S1=80.0),
        _card("c2", 80.0, S1=80.0),
        _card("c3", 60.0, S1=60.0),
        _card("c4", 60.0, S1=60.0),
    ]
    demographics = {"c1": "A", "c2": "A", "c3": "B", "c4": "B"}
    report = compute_adverse_impact_report(cards, demographics, weights={"S1": 100.0})
    for group in report.groups:
        assert group.fisher_exact_p_value is not None
        assert 0.0 <= group.fisher_exact_p_value <= 1.0
        if group.impact_ratio_ci_95_low is not None:
            assert group.impact_ratio_ci_95_low <= group.impact_ratio_ci_95_high


def test_zero_reference_selection_rate() -> None:
    """When the reference group has zero selections, the impact ratio is None."""
    cards = [
        _card("c1", 60.0, S1=60.0),
        _card("c2", 80.0, S1=80.0),
    ]
    demographics = {"c1": "A", "c2": "B"}
    report = compute_adverse_impact_report(
        cards, demographics, weights={"S1": 100.0}, reference_group="A"
    )
    group_b = next(g for g in report.groups if g.group == "B")
    assert group_b.impact_ratio is None
    assert group_b.impact_ratio_ci_95_low is None


def test_composite_without_dimension_redistributes_weights() -> None:
    """A missing sub-score is ignored and its weight is redistributed."""
    card = ScoreCard(
        candidate_id="c1",
        job_id="job_test",
        run_id="run_test",
        composite=70.0,
        selected=False,
        sub_scores={
            "S1": SubScore(dimension="S1", value=80.0),
            "S2": SubScore(dimension="S2", value=None),
        },
    )
    report = compute_adverse_impact_report([card], {"c1": "A"}, weights={"S1": 50.0, "S2": 50.0})
    group = report.groups[0]
    # With S2 missing, only S1 contributes, so leave-one-out for S1 is 0.0.
    assert group.leave_one_out_composite["S1"] == 0.0
    # Leave-one-out for S2 is the same as the full composite because S2 is absent.
    assert group.leave_one_out_composite["S2"] == 80.0


@given(st.integers(min_value=0, max_value=100), st.integers(min_value=1, max_value=100))
def test_selection_rate_between_zero_and_one(selected, total) -> None:
    """Selection rates are always in [0, 1]."""
    cards = [_card(f"c{i}", 70.0, selected=i < selected, S1=70.0) for i in range(total)]
    demographics = {f"c{i}": "A" for i in range(total)}
    report = compute_adverse_impact_report(cards, demographics, weights={"S1": 100.0})
    group = report.groups[0]
    assert 0.0 <= group.selection_rate <= 1.0
    if group.impact_ratio is not None:
        assert group.impact_ratio >= 0.0


def test_report_models_are_json_serializable() -> None:
    """The report models can be exported to JSON for the audit path."""
    cards = [_card("c1", 75.0, S1=75.0)]
    report = compute_adverse_impact_report(cards, {"c1": "A"}, weights={"S1": 100.0})
    data = report.model_dump(mode="json")
    assert data["groups"][0]["group"] == "A"
    assert math.isclose(data["groups"][0]["mean_composite"], 75.0)
