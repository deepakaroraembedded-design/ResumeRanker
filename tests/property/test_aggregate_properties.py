from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from ats_scan.models.config import BandConfig, IntegrityConfig, ScoringConfig
from ats_scan.models.scoring import Band, ScoreCard, SubScore
from ats_scan.scoring.aggregate import aggregate
from ats_scan.scoring.bands import band
from ats_scan.scoring.tiebreak import rank


class TestAggregateProperties:
    """Hypothesis properties for aggregation (TRD §5.4)."""

    @given(
        st.dictionaries(
            st.sampled_from(["S1", "S2", "S3", "S4", "S5"]),
            st.one_of(st.none(), st.floats(min_value=0.0, max_value=100.0)),
            min_size=1,
        ),
        st.dictionaries(
            st.sampled_from(["S1", "S2", "S3", "S4", "S5"]),
            st.integers(min_value=1, max_value=10),
            min_size=1,
        ),
    )
    def test_composite_is_within_bounds(self, values: dict, weights: dict) -> None:
        sub_scores = {dim: SubScore(dimension=dim, value=val) for dim, val in values.items()}
        scoring_cfg = ScoringConfig(weights=weights)
        integrity_cfg = IntegrityConfig()
        result = aggregate(sub_scores, scoring_cfg.weights, (), scoring_cfg, integrity_cfg)
        assert 0.0 <= result.base_score <= 100.0
        assert 0.0 <= result.composite <= 100.0

    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=8, alphabet=st.characters(categories=("L", "N"))),
                st.floats(min_value=0.0, max_value=100.0),
            ),
            min_size=1,
            max_size=20,
            unique_by=lambda x: x[0],
        )
    )
    def test_ranking_is_total_order(self, items: list[tuple[str, float]]) -> None:
        cards = [
            ScoreCard(
                candidate_id=cid,
                job_id="jd",
                run_id="r",
                composite=score,
            )
            for cid, score in items
        ]
        ranked = rank(cards)
        assert len(ranked) == len(cards)
        assert len({c.rank for c in ranked}) == len(ranked)

    @given(
        st.lists(
            st.tuples(
                st.text(min_size=1, max_size=8, alphabet=st.characters(categories=("L", "N"))),
                st.floats(min_value=0.0, max_value=100.0),
            ),
            min_size=2,
            max_size=10,
            unique_by=lambda x: x[0],
        )
    )
    def test_ranking_stable_under_permutation(self, items: list[tuple[str, float]]) -> None:
        cards = [
            ScoreCard(
                candidate_id=cid,
                job_id="jd",
                run_id="r",
                composite=score,
            )
            for cid, score in items
        ]
        order_a = rank(cards)
        order_b = rank(list(reversed(cards)))
        assert [c.candidate_id for c in order_a] == [c.candidate_id for c in order_b]


class TestBandProperties:
    """Boundary properties for band assignment."""

    @given(st.floats(min_value=0.0, max_value=100.0))
    def test_band_returns_valid_enum(self, composite: float) -> None:
        cfg = BandConfig()
        result = band(composite, cfg)
        assert isinstance(result, Band)
