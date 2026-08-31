from __future__ import annotations

from datetime import date
from typing import Any

import pytest

from resume_ranker.models.resume import DatePrecision, DateValue


def _resolve_date_funcs() -> list[tuple[str, Any]]:
    from resume_ranker.scoring.dimensions import (
        s4_experience,
        s5_title,
        s6_domain,
        s9_trajectory,
    )

    return [
        ("s4_experience", s4_experience._resolve_date),
        ("s5_title", s5_title._resolve_date),
        ("s6_domain", s6_domain._resolve_date),
        ("s9_trajectory", s9_trajectory._resolve_date),
    ]


@pytest.mark.parametrize(
    ("raw", "precision", "expected"),
    [
        ("2023", DatePrecision.UNKNOWN, date(2023, 1, 1)),
        ("2023-05", DatePrecision.UNKNOWN, date(2023, 5, 1)),
        ("2023-05-15", DatePrecision.UNKNOWN, date(2023, 5, 15)),
        (None, DatePrecision.PRESENT, date(2026, 8, 29)),
        (None, DatePrecision.UNKNOWN, None),
        ("not-a-date", DatePrecision.UNKNOWN, None),
        ("2023-13-45", DatePrecision.UNKNOWN, None),
    ],
)
def test_resolve_date_variants(
    raw: object | None,
    precision: DatePrecision,
    expected: date | None,
) -> None:
    """Resolve_date must handle all common date formats used by scoring dimensions."""
    now = date(2026, 8, 29)
    value = (
        DateValue(value=raw, precision=precision)
        if raw is not None or precision is not None
        else None
    )
    for name, func in _resolve_date_funcs():
        result = func(value, now)
        assert result == expected, f"{name}: expected {expected!r}, got {result!r}"
