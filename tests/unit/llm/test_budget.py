from __future__ import annotations

import pytest

from ats_scan.llm.budget import UsageTracker


class TestUsageTracker:
    def test_add_increments_counters(self) -> None:
        tracker = UsageTracker()
        tracker.add({"prompt_tokens": 10, "completion_tokens": 5})
        assert tracker.tokens_in == 10
        assert tracker.tokens_out == 5
        assert tracker.calls == 1

    def test_cost_estimation(self) -> None:
        tracker = UsageTracker()
        tracker.add(
            {"prompt_tokens": 1_000_000, "completion_tokens": 500_000},
            price_in=1.0,
            price_out=2.0,
        )
        assert tracker.cost == pytest.approx(2.0, abs=0.001)

    def test_ignores_missing_keys(self) -> None:
        tracker = UsageTracker()
        tracker.add({})
        assert tracker.tokens_in == 0
        assert tracker.tokens_out == 0
        assert tracker.calls == 1

    def test_string_usage_values(self) -> None:
        tracker = UsageTracker()
        tracker.add({"prompt_tokens": "100"})
        assert tracker.tokens_in == 100

    def test_snapshot(self) -> None:
        tracker = UsageTracker()
        tracker.add({"prompt_tokens": 10, "completion_tokens": 5})
        tracker.retries = 3
        snap = tracker.snapshot()
        assert snap == {
            "tokens_in": 10,
            "tokens_out": 5,
            "calls": 1,
            "retries": 3,
            "cost": 0.0,
        }
