from __future__ import annotations

from typing import Any

from tests.qa.oracle._utils import clamp

DEGREE_ORDINAL: dict[str, int] = {
    "high_school": 1,
    "associate": 2,
    "bachelors": 3,
    "masters": 4,
    "doctorate": 5,
}


def _degree_level(value: str | None) -> int:
    if value is None:
        return 0
    return DEGREE_ORDINAL.get(value.lower(), 0)


def s7_education(
    education: list[dict[str, Any]],
    certifications: list[dict[str, Any]],
    requirement: dict[str, Any],
    cfg: dict[str, Any],
    relevant_years: float,
) -> float:
    """TRD §5.3.7.  S7 = 100 * clip(0.6 * edu + 0.4 * cert, 0, 1)."""
    required_level = _degree_level(requirement.get("min_level"))
    accepted_fields = {f.lower() for f in requirement.get("accepted_fields", ())}
    equivalent_ok = requirement.get("equivalent_experience_allowed", True)
    min_years = float(requirement.get("min_years", 0.0))

    edu = 0.0
    if education and required_level > 0:
        levels = [_degree_level(e.get("level")) for e in education]
        best = max(levels)
        fields = [e.get("field", "").lower() for e in education]
        if best >= required_level and any(f in accepted_fields for f in fields):
            edu = 1.00
        elif best >= required_level:
            edu = 0.80
        elif best == required_level - 1 and equivalent_ok and relevant_years >= min_years + 2:
            edu = 0.70
        else:
            edu = clamp(best / required_level, 0.20, 1.00)
    elif required_level == 0:
        edu = 1.00

    cert_total = 0.0
    cert_weighted = 0.0
    if certifications:
        for cert in certifications:
            weight = float(cert.get("weight", 1.0))
            cert_total += weight
            if cert.get("matched"):
                if cert.get("expired"):
                    factor = 0.40
                elif cert.get("in_progress"):
                    factor = 0.50
                else:
                    factor = 1.00
                cert_weighted += weight * factor

    cert_score = 1.00 if cert_total == 0 else cert_weighted / cert_total

    return 100.0 * clamp(0.6 * edu + 0.4 * cert_score, 0.0, 1.0)
