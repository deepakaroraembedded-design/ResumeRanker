from __future__ import annotations

from typing import Any

from tests.qa.oracle._utils import clamp

CRITICAL_SECTIONS = {"experience", "skills", "education"}


def s10_parseability(
    extraction: dict[str, Any],
    integrity: dict[str, Any],
    blind: bool,
    cfg: dict[str, Any],
) -> float:
    """TRD §5.3.10.  S10 = 100 minus deductions, floored at 0."""
    deductions = 0.0

    if not extraction.get("text_layer_present", True):
        deductions += 40.0
    if extraction.get("multi_column", False):
        deductions += 15.0

    missing = set(integrity.get("missing_sections", ()))
    deductions += 15.0 * min(len(missing & CRITICAL_SECTIONS), 2)

    if float(integrity.get("unparseable_date_share", 0.0)) > 0.25:
        deductions += 15.0

    if not blind and not integrity.get("contact_detected", True):
        deductions += 10.0

    return clamp(100.0 - deductions, 0.0, 100.0)
