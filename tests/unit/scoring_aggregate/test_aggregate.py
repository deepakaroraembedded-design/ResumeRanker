from __future__ import annotations

from collections.abc import Sequence

import pytest

from ats_scan.errors import ConfigurationError
from ats_scan.models.common import IntegrityFinding
from ats_scan.models.config import (
    BandConfig,
    FairnessConfig,
    IntegrityConfig,
    ScoringConfig,
)
from ats_scan.models.jobspec import JobSpec, KnockoutRule
from ats_scan.models.resume import CanonicalResume, ExtractionMetadata
from ats_scan.models.scoring import Band, Evidence, KnockoutResult, ScoreCard, SubScore
from ats_scan.scoring.aggregate import Aggregation, aggregate
from ats_scan.scoring.bands import band
from ats_scan.scoring.confidence import confidence
from ats_scan.scoring.filters import evaluate_knockouts
from ats_scan.scoring.tiebreak import rank


@pytest.fixture
def base_cfg() -> ScoringConfig:
    return ScoringConfig()


@pytest.fixture
def integrity_cfg() -> IntegrityConfig:
    return IntegrityConfig()


@pytest.fixture
def fairness_cfg() -> FairnessConfig:
    return FairnessConfig()


class TestBand:
    """Boundary tests for band assignment (TRD §5.4)."""

    @pytest.mark.parametrize(
        ("composite", "expected"),
        [
            (100.0, Band.STRONG),
            (85.0, Band.STRONG),
            (84.99, Band.GOOD),
            (70.0, Band.GOOD),
            (69.99, Band.BORDERLINE),
            (55.0, Band.BORDERLINE),
            (54.99, Band.WEAK),
            (40.0, Band.WEAK),
            (39.99, Band.NOT_A_MATCH),
            (0.0, Band.NOT_A_MATCH),
        ],
    )
    def test_band_boundaries(self, composite: float, expected: Band) -> None:
        cfg = BandConfig()
        assert band(composite, cfg) is expected


class TestAggregate:
    """Weighted aggregation with renormalisation and penalties (TRD §5.4)."""

    def _sub_scores(self, overrides: dict[str, float | None] | None = None) -> dict[str, SubScore]:
        defaults = {
            "S1": 80.0,
            "S2": 60.0,
            "S3": 70.0,
            "S4": 90.0,
            "S5": 100.0,
            "S6": 50.0,
            "S7": 75.0,
            "S8": 85.0,
            "S9": 95.0,
            "S10": 100.0,
        }
        values = dict(defaults)
        if overrides:
            values.update(overrides)
        return {
            dim: SubScore(dimension=dim, value=val if val is not None else None)
            for dim, val in values.items()
        }

    def test_simple_weighted_mean(
        self, base_cfg: ScoringConfig, integrity_cfg: IntegrityConfig
    ) -> None:
        sub_scores = self._sub_scores()
        result = aggregate(sub_scores, base_cfg.weights, (), base_cfg, integrity_cfg)
        assert isinstance(result, Aggregation)
        total = sum(base_cfg.weights[d] * sub_scores[d].value for d in sub_scores)
        assert result.base_score == pytest.approx(total / 100, abs=0.001)
        assert result.composite == result.base_score
        assert result.integrity_penalty == 0.0

    def test_unavailable_dimension_renormalises(
        self, base_cfg: ScoringConfig, integrity_cfg: IntegrityConfig
    ) -> None:
        sub_scores = self._sub_scores({"S2": None})
        weights = dict(base_cfg.weights)
        active_weight = sum(weights[d] for d in sub_scores if sub_scores[d].value is not None)
        result = aggregate(sub_scores, weights, (), base_cfg, integrity_cfg)
        expected = sum(
            round(weights[d] * sub_scores[d].value / active_weight, 2)
            for d in sub_scores
            if sub_scores[d].value is not None
        )
        assert result.base_score == pytest.approx(expected, abs=0.001)
        assert result.composite == pytest.approx(result.base_score, abs=0.001)

    def test_zero_weight_dimension_dropped(
        self, base_cfg: ScoringConfig, integrity_cfg: IntegrityConfig
    ) -> None:
        sub_scores = self._sub_scores()
        weights = dict(base_cfg.weights)
        weights["S1"] = 0.0
        result = aggregate(sub_scores, weights, (), base_cfg, integrity_cfg)
        active_weight = sum(weights[d] for d in sub_scores if weights[d] > 0)
        expected = sum(
            round(weights[d] * sub_scores[d].value / active_weight, 2)
            for d in sub_scores
            if weights[d] > 0
        )
        assert result.base_score == pytest.approx(expected, abs=0.001)

    def test_no_active_dimensions(
        self, base_cfg: ScoringConfig, integrity_cfg: IntegrityConfig
    ) -> None:
        sub_scores = {dim: SubScore(dimension=dim, value=None) for dim in base_cfg.weights}
        result = aggregate(sub_scores, base_cfg.weights, (), base_cfg, integrity_cfg)
        assert result.base_score == 0.0
        assert result.composite == 0.0
        assert result.band is Band.NOT_A_MATCH

    def test_integrity_penalties(
        self, base_cfg: ScoringConfig, integrity_cfg: IntegrityConfig
    ) -> None:
        sub_scores = self._sub_scores()
        findings = (
            IntegrityFinding(detector="x", code="HIDDEN_TEXT", message="hidden"),
            IntegrityFinding(detector="x", code="KEYWORD_STUFFING", message="stuffing"),
        )
        result = aggregate(sub_scores, base_cfg.weights, findings, base_cfg, integrity_cfg)
        # Default cap is 25; HIDDEN_TEXT (25) + KEYWORD_STUFFING (10) is capped to 25.
        assert result.integrity_penalty == pytest.approx(25.0, abs=0.001)
        assert result.composite == pytest.approx(result.base_score - 25.0, abs=0.001)
        assert "PENALTY_APPLIED:HIDDEN_TEXT" in result.flags
        assert "PENALTY_APPLIED:KEYWORD_STUFFING" in result.flags

    def test_integrity_penalty_cap(
        self, base_cfg: ScoringConfig, integrity_cfg: IntegrityConfig
    ) -> None:
        sub_scores = self._sub_scores()
        findings = (
            IntegrityFinding(detector="x", code="HIDDEN_TEXT", message="hidden"),
            IntegrityFinding(detector="x", code="INJECTION_ATTEMPT", message="inject"),
            IntegrityFinding(detector="x", code="KEYWORD_STUFFING", message="stuffing"),
        )
        result = aggregate(sub_scores, base_cfg.weights, findings, base_cfg, integrity_cfg)
        assert result.integrity_penalty == pytest.approx(25.0, abs=0.001)
        assert result.composite == pytest.approx(max(0.0, result.base_score - 25.0), abs=0.001)

    def test_composite_clip_at_zero(self, base_cfg: ScoringConfig) -> None:
        sub_scores = {"S1": SubScore(dimension="S1", value=10.0)}
        weights = {"S1": 100.0}
        findings = (IntegrityFinding(detector="x", code="HIDDEN_TEXT", message="hidden"),)
        integrity_cfg = IntegrityConfig(penalties={"HIDDEN_TEXT": 50}, penalty_total_cap=50)
        result = aggregate(sub_scores, weights, findings, base_cfg, integrity_cfg)
        assert result.composite == 0.0

    def test_worked_example_trd_5_8(self) -> None:
        """TRD §5.8 worked example must produce composite 87.06 exactly."""
        scoring_cfg = ScoringConfig()
        integrity_cfg = IntegrityConfig()
        sub_scores = {
            "S1": SubScore(dimension="S1", value=88.4),
            "S2": SubScore(dimension="S2", value=60.0),
            "S3": SubScore(dimension="S3", value=79.1),
            "S4": SubScore(dimension="S4", value=92.0),
            "S5": SubScore(dimension="S5", value=100.0),
            "S6": SubScore(dimension="S6", value=100.0),
            "S7": SubScore(dimension="S7", value=84.0),
            "S8": SubScore(dimension="S8", value=96.3),
            "S9": SubScore(dimension="S9", value=100.0),
            "S10": SubScore(dimension="S10", value=100.0),
        }
        result = aggregate(sub_scores, scoring_cfg.weights, (), scoring_cfg, integrity_cfg)
        assert result.composite == pytest.approx(87.06, abs=0.005)
        assert result.base_score == pytest.approx(87.06, abs=0.005)
        assert result.band is Band.STRONG


class TestConfidence:
    """Confidence formula per TRD §5.5."""

    def _resume(self, parse_completeness: float = 1.0, ocr: float | None = None) -> CanonicalResume:
        meta = ExtractionMetadata(method="fake")
        if ocr is not None:
            meta.ocr_confidence = ocr
        return CanonicalResume(
            candidate_id="c_test",
            parse_completeness=parse_completeness,
            extraction=meta,
        )

    def test_deterministic_mode_full_confidence(self) -> None:
        resume = self._resume()
        sub_scores = {
            "S1": SubScore(
                dimension="S1", value=80.0, evidence=(Evidence(span=(0, 5), quote="text"),)
            )
        }
        assert confidence(resume, sub_scores, "deterministic") == pytest.approx(1.0, abs=0.01)

    def test_hybrid_model_agreement(self) -> None:
        resume = self._resume()
        sub_scores = {
            "S1": SubScore(
                dimension="S1", value=80.0, evidence=(Evidence(span=(0, 5), quote="text"),)
            )
        }
        c = confidence(resume, sub_scores, "hybrid", rubric_stdev=5.0)
        model_agreement = 1.0 - 5.0 / 25.0
        expected = 0.30 + 0.25 + 0.25 + 0.20 * model_agreement
        assert c == pytest.approx(expected, abs=0.01)

    def test_low_confidence_threshold(self) -> None:
        resume = self._resume(parse_completeness=0.0)
        sub_scores: dict[str, SubScore] = {}
        c = confidence(resume, sub_scores, "deterministic")
        # With no parse data the model-agreement and extraction-quality terms
        # still contribute 0.25 + 0.20 = 0.45 per TRD §5.5.
        assert c == pytest.approx(0.45, abs=0.01)

    def test_s3_detail_rubric_stdev(self) -> None:
        resume = self._resume()
        sub_scores = {
            "S3": SubScore(dimension="S3", value=70.0, detail={"rubric_stdev": 2.5}),
        }
        c = confidence(resume, sub_scores, "hybrid")
        assert c == pytest.approx(0.30 + 0.25 + 0.0 + 0.20 * (1.0 - 2.5 / 25.0), abs=0.01)


class TestTieBreak:
    """Deterministic ranking per TRD §5.6."""

    def _card(
        self,
        candidate_id: str,
        composite: float,
        s1: float = 0.0,
        s4: float = 0.0,
        confidence_value: float = 0.0,
    ) -> ScoreCard:
        return ScoreCard(
            candidate_id=candidate_id,
            job_id="jd",
            run_id="r",
            composite=composite,
            confidence=confidence_value,
            sub_scores={
                "S1": SubScore(dimension="S1", value=s1),
                "S4": SubScore(dimension="S4", value=s4),
            },
        )

    def test_rank_by_composite_descending(self) -> None:
        cards = [
            self._card("c_b", 70.0),
            self._card("c_a", 90.0),
            self._card("c_c", 80.0),
        ]
        ranked = rank(cards)
        assert [c.candidate_id for c in ranked] == ["c_a", "c_c", "c_b"]
        assert [c.rank for c in ranked] == [1, 2, 3]

    def test_tie_break_by_s1(self) -> None:
        cards = [
            self._card("c_a", 80.0, s1=70.0),
            self._card("c_b", 80.0, s1=90.0),
        ]
        ranked = rank(cards)
        assert [c.candidate_id for c in ranked] == ["c_b", "c_a"]

    def test_tie_break_by_s4(self) -> None:
        cards = [
            self._card("c_a", 80.0, s1=70.0, s4=60.0),
            self._card("c_b", 80.0, s1=70.0, s4=80.0),
        ]
        ranked = rank(cards)
        assert [c.candidate_id for c in ranked] == ["c_b", "c_a"]

    def test_tie_break_by_confidence(self) -> None:
        cards = [
            self._card("c_a", 80.0, s1=70.0, s4=60.0, confidence_value=0.70),
            self._card("c_b", 80.0, s1=70.0, s4=60.0, confidence_value=0.90),
        ]
        ranked = rank(cards)
        assert [c.candidate_id for c in ranked] == ["c_b", "c_a"]

    def test_tie_break_by_candidate_id(self) -> None:
        cards = [
            self._card("c_b", 80.0, s1=70.0, s4=60.0, confidence_value=0.80),
            self._card("c_a", 80.0, s1=70.0, s4=60.0, confidence_value=0.80),
        ]
        ranked = rank(cards)
        assert [c.candidate_id for c in ranked] == ["c_a", "c_b"]

    def test_stable_under_input_permutation(self) -> None:
        cards = [
            self._card("c_b", 80.0, s1=70.0, s4=60.0, confidence_value=0.80),
            self._card("c_a", 80.0, s1=70.0, s4=60.0, confidence_value=0.80),
            self._card("c_c", 90.0),
        ]
        orderings = [
            rank(cards),
            rank(reversed(cards)),
            rank([cards[1], cards[2], cards[0]]),
        ]
        for o in orderings:
            assert [c.candidate_id for c in o] == ["c_c", "c_a", "c_b"]


class TestKnockouts:
    """Hard filter evaluation per TRD §5.2."""

    def _resume(self) -> CanonicalResume:
        return CanonicalResume(candidate_id="c_test")

    def _spec(self, rules: Sequence[KnockoutRule]) -> JobSpec:
        return JobSpec(job_id="jd", title="Job", knockouts=tuple(rules))

    def test_pass_keeps_eligible(self, fairness_cfg: FairnessConfig) -> None:
        resume = self._resume()
        spec = self._spec([KnockoutRule(id="KO_AUTH", rule="has work authorisation")])
        result = evaluate_knockouts(resume, spec, fairness_cfg)
        assert result[0] is True
        assert result[1][0].verdict == "UNVERIFIED"

    def test_fail_excludes(self, fairness_cfg: FairnessConfig) -> None:
        resume = self._resume()
        spec = self._spec([KnockoutRule(id="KO_AUTH", rule="has work authorisation")])

        def fail_evaluator(
            rule: KnockoutRule, resume: CanonicalResume, spec: JobSpec
        ) -> KnockoutResult:
            return KnockoutResult(id=rule.id, verdict="FAIL")

        result = evaluate_knockouts(
            resume, spec, fairness_cfg, evaluators={"KO_AUTH": fail_evaluator}
        )
        assert result[0] is False
        assert result[1][0].verdict == "FAIL"

    def test_unverified_stays_eligible(self, fairness_cfg: FairnessConfig) -> None:
        resume = self._resume()
        spec = self._spec([KnockoutRule(id="KO_AUTH", rule="has work authorisation")])
        result = evaluate_knockouts(resume, spec, fairness_cfg)
        assert result[0] is True
        assert result[1][0].verdict == "UNVERIFIED"

    def test_forbidden_attribute_raises(self, fairness_cfg: FairnessConfig) -> None:
        resume = self._resume()
        spec = self._spec([KnockoutRule(id="KO_AGE", rule="age under 30")])
        with pytest.raises(ConfigurationError):
            evaluate_knockouts(resume, spec, fairness_cfg)

    def test_explicit_pass_eligible(self, fairness_cfg: FairnessConfig) -> None:
        resume = self._resume()
        spec = self._spec([KnockoutRule(id="KO_AUTH", rule="has work authorisation")])

        def pass_evaluator(
            rule: KnockoutRule, resume: CanonicalResume, spec: JobSpec
        ) -> KnockoutResult:
            return KnockoutResult(id=rule.id, verdict="PASS")

        result = evaluate_knockouts(
            resume, spec, fairness_cfg, evaluators={"KO_AUTH": pass_evaluator}
        )
        assert result[0] is True
        assert result[1][0].verdict == "PASS"
