from __future__ import annotations

from typing import Any

from tests.qa.oracle._utils import get_cfg


def band(composite: float, cfg: dict[str, Any]) -> str:
    """TRD §5.4.  Composite band thresholds."""
    thresholds = cfg.get("bands", {})
    if composite >= get_cfg(thresholds, "strong", default=85.0):
        return "strong"
    if composite >= get_cfg(thresholds, "good", default=70.0):
        return "good"
    if composite >= get_cfg(thresholds, "borderline", default=55.0):
        return "borderline"
    if composite >= get_cfg(thresholds, "weak", default=40.0):
        return "weak"
    return "not_a_match"
