from __future__ import annotations

from tests.qa.oracle._utils import clamp


def confidence(
    parse_completeness: float,
    extraction_quality: float,
    evidence_density: float,
    rubric_samples: list[float] | None,
    deterministic: bool = False,
) -> float:
    """TRD §5.5.  C = 0.3*parse + 0.25*quality + 0.25*density + 0.20*model_agreement."""
    if deterministic or not rubric_samples or len(rubric_samples) < 2:
        model_agreement = 1.0
    else:
        mean = sum(rubric_samples) / len(rubric_samples)
        variance = sum((x - mean) ** 2 for x in rubric_samples) / len(rubric_samples)
        stdev = variance**0.5
        model_agreement = clamp(1.0 - stdev / 25.0, 0.0, 1.0)

    evidence_density = clamp(evidence_density, 0.0, 1.0)
    return (
        0.30 * parse_completeness
        + 0.25 * extraction_quality
        + 0.25 * evidence_density
        + 0.20 * model_agreement
    )
