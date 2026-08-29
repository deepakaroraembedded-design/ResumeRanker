from __future__ import annotations

import re
from calendar import monthrange
from datetime import date, datetime
from typing import Final

from ats_scan.models.resume import DatePrecision, DateValue

# Month name aliases handled by the parser.
_MONTH_NAMES: Final[dict[str, int]] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}


_PRESENT_MARKERS: Final[frozenset[str]] = frozenset(
    {"present", "current", "now", "till date", "today", "ongoing"}
)


_DATE_SEPS: Final[re.Pattern[str]] = re.compile(r"[\-\u2013\u2014\u2015\u2016/]|")


def _normalise_date_token(token: str) -> str:
    """Strip surrounding parentheses and whitespace from a date token."""
    return token.strip().strip("()[]{}").strip()


def _month_to_int(month_str: str) -> int | None:
    """Convert a month name or abbreviation to a 1-based month number."""
    cleaned = month_str.strip().lower().rstrip(".")
    return _MONTH_NAMES.get(cleaned)


def _parse_year(year_str: str) -> int | None:
    """Parse a two- or four-digit year, returning a four-digit year."""
    year_str = year_str.strip()
    if not year_str.isdigit():
        return None
    year = int(year_str)
    if year < 50:
        return 2000 + year
    if year < 100:
        return 1900 + year
    return year


def _present_token(token: str) -> bool:
    """Return True if the token resolves to the present/run date."""
    return _normalise_date_token(token).lower() in _PRESENT_MARKERS


def parse_date(text: str, now: date | None = None) -> DateValue | None:
    """Parse a free-text date into a DateValue.

    Implements TRD §3.3 FR-303: MM/YYYY, Mon YYYY, Month YYYY, YYYY, MM-YYYY,
    and resolves Present/Current/Till date to the run date. Unknown tokens are
    returned as None so callers do not fabricate dates.
    """
    token = _normalise_date_token(text)
    if not token:
        return None
    lower = token.lower()
    if lower in _PRESENT_MARKERS:
        if now is None:
            return None
        return DateValue(
            value=now.isoformat(),
            precision=DatePrecision.PRESENT,
        )

    # YYYY--YYYY or YYYY-YYYY ranges: only the start token is passed here.
    # Try strict YYYY first.
    if re.fullmatch(r"\d{4}", token):
        return DateValue(
            value=f"{int(token):04d}-01-01",
            precision=DatePrecision.YEAR,
        )

    # MM/YYYY or MM-YYYY.
    match = re.fullmatch(r"(\d{1,2})[\-/](\d{4})", token)
    if match:
        month = int(match.group(1))
        year = int(match.group(2))
        if 1 <= month <= 12:
            return DateValue(
                value=f"{year:04d}-{month:02d}-01",
                precision=DatePrecision.MONTH,
            )
        return None

    # Mon YYYY or Month YYYY (allow extra spaces and two-digit years).
    match = re.fullmatch(r"([a-zA-Z\.]+)\s+(\d{2,4})", token)
    if match:
        parsed_month = _month_to_int(match.group(1))
        parsed_year = _parse_year(match.group(2))
        if parsed_month is not None and parsed_year is not None:
            return DateValue(
                value=f"{parsed_year:04d}-{parsed_month:02d}-01",
                precision=DatePrecision.MONTH,
            )
        return None

    # Day Month YYYY (accept but downgrade precision to month for simplicity).
    match = re.fullmatch(r"(\d{1,2})\s+([a-zA-Z\.]+)\s+(\d{2,4})", token)
    if match:
        day = int(match.group(1))
        parsed_month = _month_to_int(match.group(2))
        parsed_year = _parse_year(match.group(3))
        if parsed_month is not None and parsed_year is not None:
            if 1 <= day <= monthrange(parsed_year, parsed_month)[1]:
                return DateValue(
                    value=f"{parsed_year:04d}-{parsed_month:02d}-{day:02d}",
                    precision=DatePrecision.DAY,
                )
            return None
        return None

    return None


def _split_range(text: str) -> tuple[str, str] | None:
    """Split a date range string into start and end tokens."""
    # Use en/em dash or hyphen as separators; also accept "to" and "through".
    for sep in (r"\s*\-\s*", r"\s*\u2013\s*", r"\s*\u2014\s*", r"\s*\u2015\s*"):
        match = re.search(sep, text)
        if match:
            start = text[: match.start()].strip()
            end = text[match.end() :].strip()
            return start, end
    for word in (" to ", " through ", " - ", " – ", " — "):
        if word in text:
            start, end = text.split(word, 1)
            return start.strip(), end.strip()
    return None


def parse_date_range(text: str, now: date | None = None) -> tuple[DateValue, DateValue] | None:
    """Parse a date range such as 'Jan 2020 – Present'.

    Returns (start, end) DateValues or None if the start cannot be parsed.
    """
    split = _split_range(text)
    if not split:
        start = parse_date(text, now=now)
        if start is None:
            return None
        return start, DateValue(value=None, precision=DatePrecision.UNKNOWN)
    start_text, end_text = split
    start = parse_date(start_text, now=now)
    if start is None:
        return None
    end = parse_date(end_text, now=now)
    if end is None:
        end = DateValue(value=None, precision=DatePrecision.UNKNOWN)
    return start, end


def date_to_month(value: DateValue | None) -> int | None:
    """Convert a DateValue to months since 0000-01-01, or None if unavailable."""
    if value is None or value.value is None:
        return None
    try:
        dt = datetime.fromisoformat(value.value).date()
    except ValueError:
        return None
    return dt.year * 12 + (dt.month - 1)


def month_range(start: DateValue, end: DateValue | None, now: date) -> int:
    """Return the number of months covered by a start..end pair, inclusive."""
    start_month = date_to_month(start)
    if start_month is None:
        return 0
    end_month = date_to_month(end)
    if end_month is None:
        end_month = now.year * 12 + (now.month - 1)
    if end_month < start_month:
        return 0
    return end_month - start_month + 1


def calendar_union(intervals: list[tuple[int, int]]) -> int:
    """Return the total months covered by a list of intervals, without double counting.

    TRD §3.3 FR-304: overlapping and concurrent roles are reconciled so that
    total experience is never double counted. Intervals are [start, end] inclusive
    in months-since-epoch. The function is a pure, order-independent function of
    the input set of intervals.
    """
    if not intervals:
        return 0
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if start > end:
            continue
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return sum(end - start + 1 for start, end in merged)
