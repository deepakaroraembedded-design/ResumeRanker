from __future__ import annotations

from datetime import date

import pytest
from tests.qa import oracle


@pytest.mark.covers("FR-701")
def test_s1_weighted_mean_with_exact_match() -> None:
    """S1 is a weighted mean of per-skill match products."""
    required = [
        {"canonical": "python", "weight": 5},
        {"canonical": "spark", "weight": 5},
    ]
    evidence = {
        "python": [{"route": "exact", "proficiency": "applied_long", "last_used": "2026-08"}],
        "spark": [{"route": "exact", "proficiency": "listed_corroborated", "last_used": "2026-08"}],
    }
    score = oracle.s1_required_skills(required, evidence, {}, date(2026, 8, 29))
    assert score == pytest.approx(90.0, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s2_same_formula_as_s1_for_preferred() -> None:
    preferred = [{"canonical": "kafka", "weight": 3}]
    evidence = {
        "kafka": [{"route": "exact", "proficiency": "listed_only", "last_used": "2026-08"}],
    }
    score = oracle.s2_preferred_skills(preferred, evidence, {}, date(2026, 8, 29))
    assert score == pytest.approx(55.0, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s3_pool_calibration_below_min_pool() -> None:
    jd_chunks = [{"weight": 1}, {"weight": 1}]
    similarities = [[0.9, 0.8], [0.5, 0.6]]
    score = oracle.s3_semantic(
        jd_chunks,
        similarities,
        pool_raw_scores=[],
        llm_rubric_score=80.0,
        cfg={},
        deterministic=False,
    )
    # raw = (0.9 + 0.6) / 2 = 0.75, which clips to cal=1.0, so S3 = 60 + 32 = 92.
    assert score == pytest.approx(92.0, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s4_falls_in_minimum_gap() -> None:
    roles = [
        {
            "start": "2020-01",
            "end": "2026-08",
            "title_sim": 1.0,
            "skill_overlap": 1.0,
            "domain_sim": 1.0,
        }
    ]
    requirement = {"min_years": 5, "target_years": 8}
    score = oracle.s4_experience(roles, requirement, {}, date(2026, 8, 29))
    assert 70.0 <= score <= 100.0


@pytest.mark.covers("FR-701")
def test_s5_title_reaches_one_for_exact_match() -> None:
    roles = [
        {"title_sim": 1.0, "seniority_factor": 1.0, "end": "2026-08"},
    ]
    score = oracle.s5_title(roles, {}, date(2026, 8, 29))
    assert score == pytest.approx(100.0, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s6_exact_sector_match() -> None:
    roles = [{"domain_match": "exact", "end": "2026-08"}]
    score = oracle.s6_domain(roles, {}, date(2026, 8, 29))
    assert score == pytest.approx(100.0, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s7_degree_meets_requirement() -> None:
    education = [{"level": "bachelors", "field": "computer science"}]
    requirement = {
        "min_level": "bachelors",
        "accepted_fields": ["computer science"],
        "equivalent_experience_allowed": True,
        "min_years": 5,
    }
    score = oracle.s7_education(education, [], requirement, {}, 7.0)
    assert score == pytest.approx(100.0, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s8_recency_of_top_skills() -> None:
    required = [
        {"canonical": "python", "weight": 5},
        {"canonical": "sql", "weight": 5, "timeless": True},
    ]
    evidence = {
        "python": [{"last_used": "2026-08"}],
        "sql": [{"last_used": "2026-08"}],
    }
    score = oracle.s8_skill_recency(required, evidence, {}, date(2026, 8, 29))
    assert score == pytest.approx(100.0, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s9_insufficient_history_is_neutral() -> None:
    score = oracle.s9_trajectory([], {}, {}, date(2026, 8, 29))
    # Trajectory is neutral (0.70), stability is lowest band (0.45).
    expected = 100.0 * (0.5 * 0.70 + 0.5 * 0.45)
    assert score == pytest.approx(expected, abs=1e-6)


@pytest.mark.covers("FR-701")
def test_s10_flawless_native_pdf() -> None:
    extraction = {"text_layer_present": True, "multi_column": False}
    integrity = {"missing_sections": [], "unparseable_date_share": 0.0, "contact_detected": True}
    score = oracle.s10_parseability(extraction, integrity, False, {})
    assert score == pytest.approx(100.0, abs=1e-6)


@pytest.mark.covers("FR-702")
def test_aggregate_renormalises_when_dimension_unavailable() -> None:
    sub_scores = {"S1": 80.0, "S2": None, "S3": 50.0}
    weights = {"S1": 30, "S2": 8, "S3": 18}
    result = oracle.aggregate(sub_scores, weights, {}, {})
    expected = (30 * 80.0 + 18 * 50.0) / (30 + 18)
    assert result["composite"] == pytest.approx(expected, abs=1e-6)


@pytest.mark.covers("FR-803")
def test_bands_at_boundaries() -> None:
    assert oracle.band(85.0, {}) == "strong"
    assert oracle.band(70.0, {}) == "good"
    assert oracle.band(55.0, {}) == "borderline"
    assert oracle.band(40.0, {}) == "weak"
    assert oracle.band(39.9, {}) == "not_a_match"


@pytest.mark.covers("FR-704")
def test_confidence_deterministic_is_one() -> None:
    c = oracle.confidence(1.0, 1.0, 1.0, [70.0, 80.0], deterministic=True)
    assert c == pytest.approx(1.0, abs=1e-6)


@pytest.mark.covers("FR-801")
def test_tiebreak_sorts_by_candidate_id() -> None:
    candidates = [
        {"candidate_id": "b", "composite": 80.0, "S1": 70.0, "S4": 60.0, "confidence": 0.9},
        {"candidate_id": "a", "composite": 80.0, "S1": 70.0, "S4": 60.0, "confidence": 0.9},
    ]
    ranked = oracle.rank_candidates(candidates)
    assert [c["candidate_id"] for c in ranked] == ["a", "b"]
