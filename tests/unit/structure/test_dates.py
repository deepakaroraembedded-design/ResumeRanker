from __future__ import annotations

from datetime import date

from hypothesis import given
from hypothesis.strategies import integers, lists

from ats_scan.models.resume import DatePrecision, DateValue
from ats_scan.structure.dates import calendar_union, month_range, parse_date, parse_date_range


class TestParseDate:
    """Tests for date parsing per TRD §3.3 FR-303."""

    def test_present_resolves_to_now(self) -> None:
        now = date(2026, 8, 29)
        value = parse_date("Present", now=now)
        assert value is not None
        assert value.value == "2026-08-29"
        assert value.precision == DatePrecision.PRESENT

    def test_current_resolves_to_now(self) -> None:
        now = date(2026, 8, 29)
        value = parse_date("Current", now=now)
        assert value is not None
        assert value.value == "2026-08-29"

    def test_till_date_resolves_to_now(self) -> None:
        now = date(2026, 8, 29)
        value = parse_date("Till date", now=now)
        assert value is not None
        assert value.value == "2026-08-29"

    def test_mm_yyyy(self) -> None:
        value = parse_date("06/2020")
        assert value is not None
        assert value.value == "2020-06-01"
        assert value.precision == DatePrecision.MONTH

    def test_mon_yyyy(self) -> None:
        value = parse_date("Jun 2020")
        assert value is not None
        assert value.value == "2020-06-01"
        assert value.precision == DatePrecision.MONTH

    def test_month_yyyy(self) -> None:
        value = parse_date("June 2020")
        assert value is not None
        assert value.value == "2020-06-01"
        assert value.precision == DatePrecision.MONTH

    def test_yyyy(self) -> None:
        value = parse_date("2020")
        assert value is not None
        assert value.value == "2020-01-01"
        assert value.precision == DatePrecision.YEAR

    def test_mm_dash_yyyy(self) -> None:
        value = parse_date("06-2020")
        assert value is not None
        assert value.value == "2020-06-01"
        assert value.precision == DatePrecision.MONTH

    def test_yyyy_dash_dash_yyyy(self) -> None:
        pair = parse_date_range("2020–2025")
        assert pair is not None
        start, end = pair
        assert start.value == "2020-01-01"
        assert end.value == "2025-01-01"

    def test_invalid_returns_none(self) -> None:
        assert parse_date("not a date") is None

    def test_no_present_without_now(self) -> None:
        assert parse_date("Present") is None


class TestParseDateRange:
    """Tests for date range parsing."""

    def test_range_with_present(self) -> None:
        now = date(2026, 8, 29)
        pair = parse_date_range("2020 – Present", now=now)
        assert pair is not None
        start, end = pair
        assert start.value == "2020-01-01"
        assert end.precision == DatePrecision.PRESENT

    def test_range_to(self) -> None:
        pair = parse_date_range("Jan 2020 to Dec 2024")
        assert pair is not None
        start, end = pair
        assert start.value == "2020-01-01"
        assert end.value == "2024-12-01"

    def test_single_date(self) -> None:
        pair = parse_date_range("2020")
        assert pair is not None
        start, end = pair
        assert start.value == "2020-01-01"
        assert end.value is None


class TestCalendarUnion:
    """Tests for calendar-union timeline coverage."""

    def test_non_overlapping(self) -> None:
        assert calendar_union([(0, 11), (12, 23)]) == 24

    def test_overlapping_not_double_counted(self) -> None:
        assert calendar_union([(0, 11), (6, 17)]) == 18

    def test_concurrent_roles(self) -> None:
        # Two overlapping 5-year roles should count as 5 years, not 10.
        months_2020_2024 = (2020 * 12, 2024 * 12 + 11)
        months_2021_2025 = (2021 * 12, 2025 * 12 + 11)
        assert calendar_union([months_2020_2024, months_2021_2025]) == 6 * 12

    def test_empty(self) -> None:
        assert calendar_union([]) == 0

    def test_order_independent(self) -> None:
        intervals = [(12, 23), (0, 11), (6, 17)]
        assert calendar_union(intervals) == calendar_union(list(reversed(intervals)))

    def test_invalid_intervals_ignored(self) -> None:
        assert calendar_union([(0, 11), (20, 5)]) == 12

    @given(lists(integers(min_value=0, max_value=100), min_size=2, max_size=20))
    def test_union_leq_sum(self, endpoints: list[int]) -> None:
        intervals = [
            (min(a, b), max(a, b)) for a, b in zip(endpoints[::2], endpoints[1::2], strict=False)
        ]
        total_span = sum(end - start + 1 for start, end in intervals)
        assert calendar_union(intervals) <= total_span


class TestMonthRange:
    """Tests for month range computation."""

    def test_open_end(self) -> None:
        start = parse_date("2020")
        assert start is not None
        end = parse_date("not a date")
        # end is None, so range is computed to now
        now = date(2021, 6, 1)
        assert month_range(start, end, now) == 18

    def test_end_before_start(self) -> None:
        start = parse_date("2025")
        assert start is not None
        end = parse_date("2020")
        assert end is not None
        now = date(2026, 1, 1)
        assert month_range(start, end, now) == 0

    def test_bad_start(self) -> None:
        bad = DateValue(value="not-a-date")
        assert month_range(bad, None, date(2021, 6, 1)) == 0


class TestParseDateEdgeCases:
    """Additional date parsing coverage."""

    def test_two_digit_year(self) -> None:
        value = parse_date("Jan 20")
        assert value is not None
        assert value.value == "2020-01-01"

    def test_invalid_month(self) -> None:
        assert parse_date("13/2020") is None

    def test_invalid_year(self) -> None:
        assert parse_date("Jan abcd") is None

    def test_day_month_year(self) -> None:
        value = parse_date("15 June 2020")
        assert value is not None
        assert value.value == "2020-06-15"
        assert value.precision == DatePrecision.DAY

    def test_invalid_day(self) -> None:
        assert parse_date("31 June 2020") is None

    def test_empty_token(self) -> None:
        assert parse_date("   ") is None

    def test_parentheses(self) -> None:
        value = parse_date("(2020)")
        assert value is not None
        assert value.value == "2020-01-01"

    def test_range_split_none(self) -> None:
        assert parse_date_range("just text") is None

    def test_range_with_through(self) -> None:
        pair = parse_date_range("2020 through 2025")
        assert pair is not None
        start, end = pair
        assert start.value == "2020-01-01"
        assert end.value == "2025-01-01"
